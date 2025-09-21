# MicroTutor Deployment Guide

## Overview

MicroTutor now includes automatic API validation during deployment to ensure the configured API (Azure or Personal OpenAI) is working before the application starts.

## Render Configuration

### 1. Build Command

```bash
pip install -r requirements.txt
```

### 2. Start Command

```bash
./start.sh
```

### 3. Environment Variables

Set these in your Render dashboard:

#### Required Variables

- `USE_AZURE_OPENAI` - Set to `true` for Azure OpenAI or `false` for Personal OpenAI

#### For Azure OpenAI (when USE_AZURE_OPENAI=true)

- `AZURE_OPENAI_ENDPOINT` - Your Azure OpenAI endpoint
- `AZURE_OPENAI_API_KEY` - Your Azure OpenAI API key
- `AZURE_OPENAI_API_VERSION` - API version (default: 2025-04-16)
- `AZURE_OPENAI_O4_MINI_DEPLOYMENT` - Deployment name (default: o4-mini-0416)

#### For Personal OpenAI (when USE_AZURE_OPENAI=false)

- `OPENAI_API_KEY` - Your Personal OpenAI API key

#### Database

- `GLOBAL_DATABASE_URL` - Your PostgreSQL connection string

#### Optional Configuration

- `DEFAULT_MAX_TOKENS` - Override default max tokens (default: 16000)
- `VALIDATION_MAX_TOKENS` - Override validation max tokens (default: 100)

## Deployment Process

1. **Validation Phase**: The deployment script first runs `validate_deployment.py`
   - Checks that the correct credentials are present
   - Makes a test API call to verify connectivity
   - Reports response time and success

2. **Application Phase**: If validation passes, starts the main application
   - Uses the validated API configuration
   - Starts the web server on the configured port

## Validation Output

### Successful Deployment

```
🔍 Validating API configuration...
📋 Configuration:
   USE_AZURE_OPENAI: false
   Azure endpoint: ❌ Missing
   Azure API key: ❌ Missing
   OpenAI API key: ✅ Set
✅ Personal OpenAI API key found
🧪 Testing API connection...
✅ API test successful!
   Model: gpt-5-mini-2025-08-07
   Response time: 1.23s
   Response: API test successful
✅ Deployment validation PASSED!
🎉 Ready to start MicroTutor application
```

### Failed Deployment

```
❌ ERROR: Personal OpenAI selected but API key missing!
❌ Deployment validation FAILED!
💥 Cannot start application - fix configuration issues
```

## Troubleshooting

### Common Issues

1. **Missing API Key**: Ensure the correct API key is set for your chosen provider
2. **Wrong Toggle**: Check that `USE_AZURE_OPENAI` matches your intended provider
3. **Network Issues**: Verify API endpoints are accessible from Render
4. **Invalid Credentials**: Test your API keys locally first

### Testing Locally

```bash
# Test the validation script
python3 validate_deployment.py

# Test the full startup process
python3 start_app.py
```

## Files Added

- `validate_deployment.py` - API validation script
- `start_app.py` - Main startup script with validation
- `start.sh` - Shell script for Render start command
- `DEPLOYMENT.md` - This documentation
