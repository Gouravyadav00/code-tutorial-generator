# Tutorial Generator

## About This Project

This project automates the generation of beginner-friendly, interactive tutorials for any codebase by analyzing the source files and their relationships. It features a FastAPI backend with user authentication, progress tracking, and downloadable final tutorial content. The frontend provides a smooth interface for login, tutorial generation, and real-time job status updates.

---

## Prerequisites

Before running this project locally, you need:

- A running **MongoDB** server (local or remote)
- A valid **Gemini API key** (for LLM calls in tutorial generation)
- Python 3 installed on your machine
- Node.js and npm installed for frontend development

---

## Setup Instructions

### 1. Clone the Repository


### 2. Create a Python Virtual Environment and Activate It
python3 -m venv myenv
source myenv/bin/activate # On Windows use: myenv\Scripts\activate

### 3. Install Python Dependencies
pip install -r requirements.txt
pip install "pymongo[srv]"

### 4. Create Your Environment Variables
Create a `.env` file in the root directory with the following content:

SECRET_KEY=your_jwt_secret_key
MONGODB_URL=your_mongodb_connection_string
DATABASE_NAME=your_database_name
GEMINI_API_KEY=your_gemini_api_key


Replace the placeholders with your actual keys and connection URI.

### 5. Start the Backend Server

Run the FastAPI backend using Uvicorn:

uvicorn backend:app --reload --host 0.0.0.0 --port 8000


This will start the backend server at `http://localhost:8000`.

### 6. Start the Frontend

In a new terminal, navigate to the frontend directory (if applicable) and run:

npm install
npm run dev


This will start the React frontend, usually at `http://localhost:3000`.

---

## Usage

- Register a new user or login with existing credentials.
- Provide a GitHub repository URL or local directory path for tutorial generation.
- Monitor the job progress and logs on the dashboard.
- Once the tutorial generation completes, download the tutorial as an HTML file.

---

## Notes

- Ensure your MongoDB server is accessible and properly secured.
- The Gemini API key is required for the language model interactions to generate tutorial content.
- Adjust file patterns and exclusions in the config as needed for different projects.

---

## License
Free to use!!

---

## Contact

For questions or contributions, please open an issue or submit a pull request.

Happy learning!

