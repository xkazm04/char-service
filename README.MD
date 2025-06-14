# Character Creator API Service

A FastAPI-based backend service for AI-powered character asset analysis and generation. This service provides intelligent image analysis, character metadata extraction, and 3D asset generation capabilities for game development and digital content creation.

## 🎯 Business Overview

The Character Creator API enables developers and content creators to:

- **Analyze Character Assets**: Upload images and extract detailed metadata about characters, including appearance, style, and attributes
- **Multi-Model AI Analysis**: Leverage OpenAI GPT-4 Vision and Google Gemini for comprehensive image understanding
- **3D Asset Generation**: Generate 3D meshes and models using Meshy API integration
- **Asset Management**: Store, search, and organize character assets with MongoDB Atlas
- **Background Processing**: Automated polling and status tracking for long-running generation tasks

### Key Features

- 🤖 **AI-Powered Analysis**: Multi-model approach using OpenAI and Google Gemini
- 🎨 **Image Processing**: Character asset detection and metadata extraction
- 🧊 **3D Generation**: Integration with Meshy API for 3D model creation
- 📊 **Asset Search**: Vector-based similarity search using MongoDB Atlas
- ⚡ **Async Processing**: Fast, concurrent request handling with FastAPI
- 🔍 **Health Monitoring**: Built-in health checks and logging
- 🐳 **Container Ready**: Docker support for easy deployment

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- MongoDB Atlas account
- API keys for:
  - OpenAI (GPT-4 Vision)
  - Google AI (Gemini)
  - Groq (optional)
  - Leonardo AI (optional)
  - Meshy 3D (optional)
  - Hugging Face (optional)

### Local Development Setup

   ```bash
   git clone <your-repo-url>
   cd char-service
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   # Install dependencies
   pip install -r requirements.txt
   # Configure vairbales
   cp .env.example .env
   # Make temp folder
   mkdir temp
   # Run dev server
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```


### Code structure
char-service/
├── main.py              # FastAPI application entry point
├── database.py          # MongoDB connection and configuration
├── requirements.txt     # Python dependencies
├── Dockerfile          # Container configuration
├── models/             # Pydantic data models
│   ├── asset.py
│   ├── character.py
│   └── generation.py
├── routes/             # API route handlers
│   ├── analyze.py      # Image analysis endpoints
│   ├── asset.py        # Asset management
│   ├── generation.py   # 3D generation
│   └── search.py       # Search functionality
├── services/           # Business logic services
│   ├── image_analyze.py    # AI image analysis
│   ├── background_polling.py  # Async task polling
│   └── atlas_*.py         # MongoDB Atlas integrations
└── utils/              # Utility functions

### API - Core endpoints
- GET /health - Service health status
- POST /analyze/ - Upload and analyze character images
- GET /assets/ - Retrieve character assets
- POST /assets/ - Create new character assets
- GET /search/ - Search assets by similarity
- POST /generation/ - Generate 3D models
- GET /generation/{id}/status - Check generation status