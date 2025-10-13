# Guideline Search - Quick Start Guide

## 🚀 5-Minute Setup

### Option 1: Use ToolUniverse (Recommended)

```bash
# 1. Install ToolUniverse
pip install tooluniverse

# 2. Test it works
python scripts/test_guideline_search.py

# 3. Start your server
python run_v4.py

# 4. Try the API
curl http://localhost:5001/api/v1/guidelines/organism/staphylococcus%20aureus
```

**Done!** You now have access to 8 guideline search tools.

### Option 2: Use Custom Tools (No ToolUniverse)

```bash
# 1. Install dependencies
pip install requests beautifulsoup4

# 2. The custom tools are already in place
# No ToolUniverse needed!

# 3. Test it works
python scripts/test_guideline_search.py

# 4. Start your server
python run_v4.py
```

**Done!** You have NICE and PubMed guideline search.

## 📖 Usage Examples

### In Python

```python
from microtutor.services.guideline_service import GuidelineService

# Initialize service
service = GuidelineService()

# Search for organism
results = await service.search_for_organism(
    organism="Staphylococcus aureus",
    treatment_focus=True
)

print(f"Found {results['total_guidelines']} guidelines")

# Get summary for LLM
summary = service.get_guideline_summary(results['results'])
print(summary)
```

### Via API

```bash
# Search guidelines
curl -X POST http://localhost:5001/api/v1/guidelines/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "MRSA treatment",
    "sources": ["NICE", "PubMed"],
    "limit": 5
  }'

# Organism-specific search
curl http://localhost:5001/api/v1/guidelines/organism/escherichia%20coli

# Check available sources
curl http://localhost:5001/api/v1/guidelines/sources

# Health check
curl http://localhost:5001/api/v1/guidelines/health
```

### In Tutoring Workflow

```python
# In your tutor_service.py

class TutorService:
    def __init__(self):
        self.guideline_service = GuidelineService()
    
    async def start_case(self, organism: str):
        # Fetch guidelines
        guidelines = await self.guideline_service.search_for_organism(
            organism=organism
        )
        
        # Add to LLM context
        context = self.guideline_service.get_guideline_summary(
            guidelines['results']
        )
        
        # Use in system prompt
        system_prompt = f"""
You are a medical tutor.

Current Clinical Guidelines:
{context}

Guide the student to discover this information.
"""
        
        return await self.chat_with_context(system_prompt)
```

## 🎯 Key Features

### Search Multiple Sources

```python
results = await service.search_guidelines(
    query="pneumonia treatment",
    sources=["NICE", "PubMed", "WHO"],  # Multiple sources
    limit=5
)
```

### Get Formatted Summary

```python
# Perfect for LLM context
summary = service.get_guideline_summary(results)

# Use in prompts
system_message = f"Based on these guidelines:\n{summary}\n..."
```

### Organism-Specific Search

```python
# Automatically constructs optimal query
results = await service.search_for_organism(
    organism="Neisseria meningitidis",
    treatment_focus=True
)
# Searches: "Neisseria meningitidis treatment guidelines"
```

## 📊 What You Get

### With ToolUniverse (8 tools)

- ✅ NICE (UK official guidelines)
- ✅ WHO (international guidelines)
- ✅ PubMed (peer-reviewed)
- ✅ Europe PMC (European research)
- ✅ TRIP Database (evidence-based)
- ✅ OpenAlex (scholarly database)
- ✅ NICE Full Text (complete guidelines)
- ✅ WHO Full Text (complete + PDFs)

### With Custom Tools (2 tools)

- ✅ NICE (UK official guidelines)
- ✅ PubMed (peer-reviewed)

## 🧪 Testing

```bash
# Run all tests
python scripts/test_guideline_search.py

# Or run specific tests
python -c "
import asyncio
from microtutor.services.guideline_service import GuidelineService

async def test():
    service = GuidelineService()
    results = await service.search_guidelines('diabetes', limit=2)
    print(f'Found {sum(len(v) for v in results.values())} guidelines')

asyncio.run(test())
"
```

## 📝 API Routes

All routes available at: `http://localhost:5001/api/v1/guidelines/`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/search` | Search all sources |
| GET | `/organism/{name}` | Search for organism |
| GET | `/sources` | List available sources |
| GET | `/health` | Check service status |

### Interactive Docs

Visit: **<http://localhost:5001/api/docs>**

- Try all endpoints directly in browser
- See request/response examples
- Auto-generated from FastAPI

## 🔧 Configuration

### Use ToolUniverse

```python
service = GuidelineService(use_tooluniverse=True)
```

### Use Custom Tools

```python
service = GuidelineService(use_tooluniverse=False)
```

### Add API Keys (Optional)

```bash
# .env
PUBMED_API_KEY=your_key_here  # Get from: https://www.ncbi.nlm.nih.gov/account/
```

```python
# In service
results = await service.search_guidelines(
    query="...",
    sources=["PubMed"],
    api_key=os.getenv("PUBMED_API_KEY")
)
```

## 💡 Tips

### 1. Enable Caching

Guidelines don't change frequently - cache results:

```python
# Already enabled in GuidelineService!
# Results cached per query for faster subsequent searches
```

### 2. Limit Results

Don't overwhelm LLMs:

```python
# Keep it focused
results = await service.search_guidelines(
    query="...",
    limit=3  # Top 3 per source
)

# Truncate summaries
summary = service.get_guideline_summary(
    results,
    max_per_source=2,          # Max 2 per source
    max_summary_length=200     # 200 chars max
)
```

### 3. Handle Failures Gracefully

```python
try:
    guidelines = await service.search_guidelines(query)
except Exception as e:
    logger.error(f"Guideline search failed: {e}")
    # Continue without guidelines
    guidelines = {}
```

### 4. Rate Limiting

Be respectful to APIs:

```python
# Already implemented in custom tools!
# - 1 second delay for NICE
# - 0.5 second delay for PubMed
```

## 🐛 Troubleshooting

### "ToolUniverse not found"

```bash
pip install tooluniverse
```

Or use custom tools:

```python
service = GuidelineService(use_tooluniverse=False)
```

### "No results found"

Try:

- More specific queries: "MRSA skin infection treatment" vs "MRSA"
- Different sources: Some organisms may not have NICE guidelines
- Check spelling: Use scientific names when possible

### "Service unavailable"

Check:

```python
service = GuidelineService()
print(service.is_available())  # Should be True
print(service.get_available_sources())  # Shows what works
```

## 📚 Next Steps

1. **Read Full Guide**: [GUIDELINE_TOOLS_INTEGRATION.md](./GUIDELINE_TOOLS_INTEGRATION.md)
2. **Integrate into Tutoring**: Add to case generation, socratic questioning
3. **Test with Real Cases**: Try with your common organisms
4. **Monitor Usage**: Track which guidelines students find helpful
5. **Expand**: Add more guideline sources from ToolUniverse

## 🔗 Resources

- **ToolUniverse Docs**: <https://zitniklab.hms.harvard.edu/ToolUniverse/>
- **Clinical Guidelines Tools**: <https://zitniklab.hms.harvard.edu/ToolUniverse/guide/clinical_guidelines_tools.html>
- **ToolUniverse GitHub**: <https://github.com/mims-harvard/ToolUniverse>
- **V4 API Docs**: <http://localhost:5001/api/docs> (when running)

## ✅ Summary

**Recommended Setup:**

```bash
# 1. Install ToolUniverse
pip install tooluniverse

# 2. Test
python scripts/test_guideline_search.py

# 3. Use in code
from microtutor.services.guideline_service import GuidelineService
service = GuidelineService()
results = await service.search_for_organism("Staphylococcus aureus")
```

**That's it!** You now have evidence-based guideline search integrated into MicroTutor V4.
