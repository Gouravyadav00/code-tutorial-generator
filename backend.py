"""
Simplified FastAPI backend for Tutorial Generator with Authentication and Progress Tracking
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
import uuid
import os
import json
from datetime import datetime, timedelta, timezone
import asyncio
from concurrent.futures import ThreadPoolExecutor
import bcrypt
from jose import JWTError, jwt
import markdown

# MongoDB imports
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

# Import the flow creation function
from flow import create_tutorial_flow

app = FastAPI(title="Tutorial Generator API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# MongoDB Configuration
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "tutorial_generator")

# Initialize MongoDB connection
try:
    client = MongoClient(
        MONGODB_URL,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=20000,
        socketTimeoutMS=30000,
        retryWrites=True,
        w='majority'
    )
    client.admin.command('ping')
    db: Database = client[DATABASE_NAME]
    users_collection: Collection = db.users
    jobs_collection: Collection = db.jobs
    print(f"✅ Connected to MongoDB at {MONGODB_URL}")
except Exception as e:
    print(f"❌ Failed to connect to MongoDB: {e}")
    users_collection = None
    jobs_collection = None

# Thread pool for running flows
executor = ThreadPoolExecutor(max_workers=3)

# Security
security = HTTPBearer()

# Pydantic Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class User(BaseModel):
    id: str
    email: str
    full_name: str
    created_at: datetime
    is_active: bool = True

class Token(BaseModel):
    access_token: str
    token_type: str

class ProjectConfig(BaseModel):
    repo_url: Optional[str] = None
    local_dir: Optional[str] = None
    project_name: Optional[str] = None
    github_token: Optional[str] = None
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    max_file_size: Optional[int] = 100000
    language: Optional[str] = "english"
    use_cache: Optional[bool] = True
    max_abstractions: Optional[int] = 10

# Helper Functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    if users_collection is not None:
        user = users_collection.find_one({"email": email})
        if user is None:
            raise credentials_exception
        return user
    else:
        raise HTTPException(status_code=500, detail="Database not available")

def run_tutorial_flow(job_id: str, config: ProjectConfig, user_id: str):
    """Run the tutorial generation flow in a background thread"""
    try:
        # Update job status
        if jobs_collection is not None:
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {"status": "processing", "progress": 0, "updated_at": datetime.now(timezone.utc)}}
            )
        
        # Prepare shared dictionary with progress callback
        def update_progress(step: str, progress: int, log_message: str = None):
            timestamp = datetime.now(timezone.utc)
            if jobs_collection is not None:
                update_data = {
                    "current_step": step, 
                    "progress": progress, 
                    "updated_at": timestamp
                }
                
                if log_message:
                    log_entry = {
                        "timestamp": timestamp,
                        "level": "INFO",
                        "message": log_message,
                        "step": step,
                        "progress": progress
                    }
                    jobs_collection.update_one(
                        {"_id": job_id},
                        {
                            "$set": update_data,
                            "$push": {"logs": log_entry}
                        }
                    )
                else:
                    jobs_collection.update_one(
                        {"_id": job_id},
                        {"$set": update_data}
                    )
        
        shared = {
            "repo_url": config.repo_url,
            "local_dir": config.local_dir,
            "project_name": config.project_name,
            "github_token": config.github_token,
            "output_dir": "output",
            "include_patterns": set(config.include_patterns) if config.include_patterns else None,
            "exclude_patterns": set(config.exclude_patterns) if config.exclude_patterns else None,
            "max_file_size": config.max_file_size,
            "language": config.language,
            "use_cache": config.use_cache,
            "max_abstraction_num": config.max_abstractions,
            "update_progress": update_progress,
        }
        
        # Create and run the flow
        tutorial_flow = create_tutorial_flow()
        tutorial_flow.run(shared)
        
        # Store the result
        result = {
            "abstractions": shared.get("abstractions", []),
            "relationships": shared.get("relationships", {}),
            "chapters": shared.get("chapters", []),
            "output_dir": shared.get("final_output_dir", ""),
        }
        
        if jobs_collection is not None:
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {
                    "status": "completed",
                    "progress": 100,
                    "result": result,
                    "completed_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
        
    except Exception as e:
        if jobs_collection is not None:
            jobs_collection.update_one(
                {"_id": job_id},
                {"$set": {
                    "status": "failed",
                    "error": str(e),
                    "progress": 0,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )

# API Routes

@app.get("/")
async def root():
    return {"message": "Tutorial Generator API", "version": "1.0.0"}

# Authentication Routes
@app.post("/auth/register", response_model=Token)
async def register(user: UserCreate):
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    # Check if user exists
    existing_user = users_collection.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    hashed_password = hash_password(user.password)
    user_doc = {
        "_id": str(uuid.uuid4()),
        "email": user.email,
        "full_name": user.full_name,
        "hashed_password": hashed_password,
        "created_at": datetime.now(timezone.utc),
        "is_active": True,
    }
    
    users_collection.insert_one(user_doc)
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/auth/login", response_model=Token)
async def login(user: UserLogin):
    if users_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    # Verify user
    db_user = users_collection.find_one({"email": user.email})
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/auth/me", response_model=User)
async def read_users_me(current_user: Dict[str, Any] = Depends(get_current_user)):
    return User(
        id=current_user["_id"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        created_at=current_user["created_at"],
        is_active=current_user["is_active"]
    )

# Tutorial Generation Routes
@app.post("/generate")
async def generate_tutorial(config: ProjectConfig, background_tasks: BackgroundTasks, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Start a new tutorial generation job"""
    job_id = str(uuid.uuid4())
    
    # Initialize job tracking
    job_doc = {
        "_id": job_id,
        "user_id": current_user["_id"],
        "status": "pending",
        "progress": 0,
        "current_step": None,
        "result": None,
        "error": None,
        "logs": [{
            "timestamp": datetime.now(timezone.utc),
            "level": "INFO",
            "message": f"Job created for repository: {config.repo_url or config.local_dir}",
            "step": "Initializing",
            "progress": 0
        }],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    
    if jobs_collection is not None:
        jobs_collection.insert_one(job_doc)
    
    # Submit the flow to run in background
    background_tasks.add_task(run_tutorial_flow, job_id, config, current_user["_id"])
    
    return {"job_id": job_id}

@app.get("/status/{job_id}")
async def get_job_status(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get the status of a tutorial generation job"""
    if jobs_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    job = jobs_collection.find_one({"_id": job_id, "user_id": current_user["_id"]})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "id": job["_id"],
        "status": job["status"],
        "progress": job["progress"],
        "current_step": job.get("current_step"),
        "result": job.get("result"),
        "error": job.get("error"),
        "logs": job.get("logs", [])
    }

@app.get("/jobs/{job_id}/download/html")
async def download_job_html(job_id: str, current_user: Dict[str, Any] = Depends(get_current_user)):
    """Download job result as HTML"""
    if jobs_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    job = jobs_collection.find_one({"_id": job_id, "user_id": current_user["_id"]})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    result = job.get("result", {})
    chapters = result.get("chapters", [])
    
    if not chapters:
        raise HTTPException(status_code=404, detail="No tutorial content found")
    
    try:
        # Combine all chapters into one markdown content
        tutorial_content = ""
        for i, chapter in enumerate(chapters):
            tutorial_content += f"{chapter}\n\n---\n\n"
        
        # Convert markdown to HTML
        html_content = markdown.markdown(tutorial_content, extensions=['tables', 'fenced_code', 'toc'])
        
        # Create full HTML document
        html_full = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tutorial - Job {job_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #2563eb;
            margin-top: 2em;
            margin-bottom: 0.5em;
        }}
        h1 {{
            border-bottom: 2px solid #e5e7eb;
            padding-bottom: 0.3em;
        }}
        code {{
            background: #f1f5f9;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
        }}
        pre {{
            background: #f8fafc;
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
            border: 1px solid #e2e8f0;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #e2e8f0;
            padding-left: 16px;
            margin: 16px 0;
            color: #6b7280;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #e2e8f0;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background: #f9fafb;
            font-weight: 600;
        }}
        .header {{
            text-align: center;
            margin-bottom: 2em;
            padding: 20px;
            background: #f8fafc;
            border-radius: 8px;
        }}
        .footer {{
            text-align: center;
            margin-top: 3em;
            padding: 20px;
            background: #f8fafc;
            border-radius: 8px;
            color: #6b7280;
        }}
        hr {{
            border: none;
            border-top: 1px solid #e2e8f0;
            margin: 2em 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Generated Tutorial</h1>
        <p><strong>Job ID:</strong> {job_id}</p>
        <p><strong>Generated:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
    </div>
    
    {html_content}
    
    <div class="footer">
        <p><em>Generated with Tutorial Generator API</em></p>
        <p>Job completed on {job.get('completed_at', datetime.now()).strftime('%B %d, %Y at %I:%M %p') if isinstance(job.get('completed_at'), datetime) else 'Unknown'}</p>
    </div>
</body>
</html>"""
        
        headers = {
            'Content-Disposition': f'attachment; filename="tutorial-{job_id}.html"',
            'Content-Type': 'text/html'
        }
        
        return Response(content=html_full, headers=headers, media_type='text/html')
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate HTML: {str(e)}")

@app.get("/jobs")
async def get_user_jobs(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get all jobs for the current user"""
    if jobs_collection is None:
        raise HTTPException(status_code=500, detail="Database not available")
    
    jobs = list(jobs_collection.find({"user_id": current_user["_id"]}).sort("created_at", -1))
    
    # Convert datetime objects to ISO strings for JSON serialization
    for job in jobs:
        job["id"] = job["_id"]
        del job["_id"]
        if "created_at" in job:
            job["created_at"] = job["created_at"].isoformat()
        if "updated_at" in job:
            job["updated_at"] = job["updated_at"].isoformat()
        if "completed_at" in job:
            job["completed_at"] = job["completed_at"].isoformat()
    
    return jobs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)