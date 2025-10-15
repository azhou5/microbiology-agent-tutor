# MicroTutor V4 Deployment Guide

This guide covers deploying MicroTutor V4 to Render.com and other production environments.

## 🚀 Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start development server
python run_v4.py
```

### Production Deployment

```bash
# Start production server
python run_production.py
```

## 📋 Prerequisites

- Python 3.10+
- PostgreSQL database (local or cloud)
- OpenAI API key OR Azure OpenAI credentials
- (Optional) FAISS for vector search

## 🔧 Environment Configuration

### Environment Variables

The application uses a hierarchical configuration system:

1. **System environment variables** (highest priority)
2. **`.env` file** (if present)
3. **`dot_env_microtutor.txt`** (V3 compatibility)
4. **Default values** (lowest priority)

### Required Variables

#### LLM Configuration (Choose One)

**Option A: Azure OpenAI**

```bash
USE_AZURE_OPENAI=true
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2025-04-16
AZURE_OPENAI_O4_MINI_DEPLOYMENT=o4-mini-0416
```

**Option B: Personal OpenAI**

```bash
USE_AZURE_OPENAI=false
OPENAI_API_KEY=your-openai-key
PERSONAL_OPENAI_MODEL=o4-mini-2025-04-16
```

#### Database Configuration (Choose One)

**Option A: Global Database (Production)**

```bash
USE_GLOBAL_DB=true
GLOBAL_DATABASE_URL=postgresql://user:password@host:port/database
```

**Option B: Local Database (Development)**

```bash
USE_LOCAL_DB=true
LOCAL_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/microbiology_feedback
```

**Option C: Individual Settings**

```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=microbiology_feedback
DB_USER=postgres
DB_PASSWORD=your-password
```

### Optional Variables

```bash
# Application Settings
DEBUG=false
SECRET_KEY=your-secret-key
LOG_LEVEL=INFO

# Feature Flags
USE_FAISS=true
OUTPUT_TOOL_DIRECTLY=true
IN_CONTEXT_LEARNING=true
REWARD_MODEL_SAMPLING=false
FAST_CLASSIFICATION_ENABLED=false

# Defaults
DEFAULT_ORGANISM=staphylococcus aureus
```

## 🌐 Render.com Deployment

### 1. Prepare Repository

Ensure your repository has:

- `requirements.txt` (production dependencies)
- `run_production.py` (production startup script)
- `render.yaml` (optional, for Blueprint deployment)

### 2. Create Render Service

#### Option A: Manual Setup

1. Connect your GitHub repository
2. Choose "Web Service"
3. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python run_production.py`
   - **Python Version**: 3.10+

#### Option B: Blueprint Deployment

1. Use the included `render.yaml`
2. Deploy via Render Blueprint
3. Configure environment variables in dashboard

### 3. Environment Variables

Set these in the Render dashboard:

**Required:**

- `USE_AZURE_OPENAI` (true/false)
- `AZURE_OPENAI_API_KEY` OR `OPENAI_API_KEY`
- `GLOBAL_DATABASE_URL` (if using global DB)

**Optional:**

- `DEBUG=false`
- `LOG_LEVEL=INFO`
- `SECRET_KEY` (auto-generated if not set)

### 4. Database Setup

#### Option A: Render PostgreSQL

1. Create a PostgreSQL database in Render
2. Use the connection string as `GLOBAL_DATABASE_URL`

#### Option B: External Database

1. Use your existing PostgreSQL database
2. Set `GLOBAL_DATABASE_URL` to your connection string

### 5. Custom Domain (Optional)

1. Go to Settings → Custom Domains
2. Add your domain
3. Configure DNS records as instructed

## 🔍 Monitoring & Logs

### Health Checks

- **Health endpoint**: `GET /health`
- **API info**: `GET /api/v1/info`

### Logs

- View logs in Render dashboard
- Logs are also available via `run_production.py`

### Performance

- Monitor response times in Render dashboard
- Check database connections
- Monitor LLM API usage

## 🛠️ Troubleshooting

### Common Issues

**1. Import Errors**

```
ModuleNotFoundError: No module named 'microtutor'
```

- Ensure `src` directory is in Python path
- Check that all dependencies are installed

**2. Database Connection Issues**

```
sqlalchemy.exc.OperationalError: could not connect to server
```

- Verify database URL is correct
- Check database is accessible from Render
- Ensure database credentials are valid

**3. LLM API Issues**

```
openai.AuthenticationError: Incorrect API key provided
```

- Verify API key is correct
- Check `USE_AZURE_OPENAI` setting
- Ensure proper endpoint configuration

**4. Environment Variable Issues**

```
KeyError: 'REQUIRED_VAR'
```

- Check all required variables are set
- Verify variable names are correct
- Check for typos in variable names

### Debug Mode

Enable debug mode for detailed error messages:

```bash
DEBUG=true
LOG_LEVEL=DEBUG
```

## 📊 Performance Optimization

### Production Settings

- Use `run_production.py` instead of `run_v4.py`
- Set `DEBUG=false`
- Use production database
- Enable caching if available

### Scaling

- Render automatically handles horizontal scaling
- Monitor resource usage
- Consider upgrading plan for high traffic

## 🔒 Security

### Environment Variables

- Never commit API keys to repository
- Use Render's secure environment variables
- Rotate keys regularly

### Database

- Use strong passwords
- Enable SSL connections
- Restrict database access

### API Security

- Configure CORS properly for production
- Use HTTPS
- Implement rate limiting if needed

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL on Render](https://render.com/docs/databases/postgresql)
- [OpenAI API Documentation](https://platform.openai.com/docs)

## 🆘 Support

For issues specific to MicroTutor V4:

1. Check the logs in Render dashboard
2. Verify environment configuration
3. Test locally with same configuration
4. Check database and API connectivity

For Render-specific issues:

1. Check Render status page
2. Review Render documentation
3. Contact Render support
