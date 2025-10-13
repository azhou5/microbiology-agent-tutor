"""
Case Generator with RAG for Medical Microbiology Tutor (V4)

This module generates realistic clinical cases using RAG (Retrieval Augmented Generation).
Adapted from V3 to work standalone in V4 structure.
"""

import os
import json
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from microtutor.agents.base_agent import BaseAgent
from openai import AzureOpenAI, OpenAI
import logging

# Try to import Qdrant and embedding libraries (optional)
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http.models import PointStruct
    from qdrant_client import models
    HAS_QDRANT = True
except ImportError:
    HAS_QDRANT = False
    print("Qdrant client not available. Will use fallback generation.")

# Load environment
load_dotenv()

class CaseGeneratorRAGAgent(BaseAgent):
    def __init__(self, model_name: str = None):
        super().__init__(model_name)
        print("Initializing CaseGeneratorRAGAgent...")
        
        # Default organism if none is specified
        self.organism = os.getenv("DEFAULT_ORGANISM", "staphylococcus")
        self.collection = "union_collection"
        
        # System prompt for case generation
        self.system_prompt = """You are an expert medical microbiologist specializing in creating realistic clinical cases.
        Generate detailed, medically accurate cases that include subtle but important diagnostic clues. Each case should be
        challenging but solvable with proper clinical reasoning."""
        
        # Output directory for saving generated cases
        self.output_dir = f"Case_Outputs"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Case cache file path
        self.case_cache_file = os.path.join(self.output_dir, "case_cache.json")
        
        # Load existing case cache
        self.case_cache = self._load_case_cache()
        
        # Initialize Qdrant client
        self.qdrant_client = None
        if HAS_QDRANT:
            try:
                self.qdrant_client = QdrantClient(
                    url=os.getenv("QDRANT_URL"),
                    api_key=os.getenv("QDRANT_API_KEY"),
                    timeout=60  # Increase timeout to 60 seconds
                )
                print("Successfully initialized Qdrant client")
            except Exception as e:
                print(f"Error initializing Qdrant client: {str(e)}")
                print("Will use fallback generation when needed")
                self.qdrant_client = None
        
        # Initialize embedding client
        use_azure_env = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if use_azure_env and azure_endpoint and azure_api_key:
            # Use Azure OpenAI
            self.embedding_client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
            )
        elif openai_api_key:
            # Use personal OpenAI
            self.embedding_client = OpenAI(api_key=openai_api_key)
        else:
            raise ValueError("Missing required OpenAI environment variables. Check USE_AZURE_OPENAI setting and credentials.")
        
        # Case sections
        self.case_sections = {
            "patient_info": "",
            "history_and_exam": "",
            "diagnostics": "",
            "diagnosis_and_treatment": ""
        }
        
        # Cache for RAG contexts to reduce API calls
        self.context_cache = {}
        
        # Counter for Qdrant API calls
        self.qdrant_call_count = 0

    def _load_case_cache(self) -> Dict[str, str]:
        """Load the case cache from file."""
        try:
            if os.path.exists(self.case_cache_file):
                with open(self.case_cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                    print(f"Loaded case cache with {len(cache)} organisms")
                    return cache
            else:
                print("No existing case cache found, starting with empty cache")
                return {}
        except Exception as e:
            print(f"Error loading case cache: {str(e)}")
            return {}

    def _save_case_cache(self):
        """Save the case cache to file."""
        try:
            with open(self.case_cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.case_cache, f, indent=2, ensure_ascii=False)
            print(f"Saved case cache with {len(self.case_cache)} organisms")
        except Exception as e:
            print(f"Error saving case cache: {str(e)}")

    def _normalize_organism_name(self, organism: str) -> str:
        """Normalize organism name for consistent cache keys."""
        return organism.lower().strip().replace(" ", "_")

    def generate_case(self, organism: str = None) -> str:
        """Generate a clinical case for the specified organism."""
        logging.info(f"[BACKEND_START_CASE] 3d. CaseGenerator's generate_case called for organism: '{organism}'.")
        if organism:
            self.organism = organism.lower()
            self.collection = "union_collection"
        
        # Normalize organism name for cache key
        cache_key = self._normalize_organism_name(self.organism)
        logging.info(f"[BACKEND_START_CASE]   - Normalized cache key is: '{cache_key}'.")
        
        # Check if case already exists in cache
        if cache_key in self.case_cache:
            logging.info(f"[BACKEND_START_CASE]   - Found cached case for '{cache_key}'. Returning it.")
            
            # Also save to the old case.txt file for backward compatibility
            case_file = os.path.join(self.output_dir, "case.txt")
            try:
                with open(case_file, 'w', encoding='utf-8') as f:
                    f.write(self.case_cache[cache_key])
            except Exception as e:
                print(f"Error saving case to case.txt: {str(e)}")
            
            return self.case_cache[cache_key]
        
        logging.info(f"[BACKEND_START_CASE]   - No cached case found for '{cache_key}', generating new case...")
        
        # Reset case sections
        self._reset_case_sections()
        
        # Reset context cache and call counter
        self.context_cache = {}
        self.qdrant_call_count = 0
        
        # Check if Qdrant is available and working
        if not self.qdrant_client or not HAS_QDRANT:
            print("No Qdrant client available, using fallback case generation")
            case_text = self._fallback_case_generation()
        else:
            # Try to get context to validate connection
            try:
                test_context = self._get_rag_context(f"Information about {self.organism}")
                if not test_context or len(test_context.strip()) < 20:
                    print("Could not retrieve sufficient context, using fallback case generation")
                    case_text = self._fallback_case_generation()
                else:
                    print("Successfully retrieved context, proceeding with RAG case generation")
                    
                    # Generate each section of the case
                    self._generate_patient_info()
                    self._generate_history_and_exam()
                    self._generate_diagnostics()
                    self._generate_diagnosis_and_treatment()
                    
                    # Combine all sections into a complete case
                    case_text = self._combine_case_sections()
                    
            except Exception as e:
                print(f"Error in RAG case generation: {str(e)}")
                case_text = self._fallback_case_generation()
        
        # Save the generated case to cache
        self.case_cache[cache_key] = case_text
        self._save_case_cache()
        
        # Also save to the old case.txt file for backward compatibility
        case_file = os.path.join(self.output_dir, "case.txt")
        try:
            with open(case_file, 'w', encoding='utf-8') as f:
                f.write(case_text)
        except Exception as e:
            print(f"Error saving case to case.txt: {str(e)}")
        
        print(f"Generated and cached new case for {self.organism}")
        return case_text

    def get_cached_organisms(self) -> List[str]:
        """Get a list of all organisms that have cached cases."""
        return list(self.case_cache.keys())

    def clear_cache(self, organism: str = None):
        """Clear the cache for a specific organism or all organisms."""
        if organism:
            cache_key = self._normalize_organism_name(organism)
            if cache_key in self.case_cache:
                del self.case_cache[cache_key]
                self._save_case_cache()
                print(f"Cleared cache for {organism}")
            else:
                print(f"No cached case found for {organism}")
        else:
            self.case_cache = {}
            self._save_case_cache()
            print("Cleared all cached cases")

    def regenerate_case(self, organism: str = None) -> str:
        """Force regeneration of a case, bypassing the cache."""
        if organism:
            self.organism = organism.lower()
        
        cache_key = self._normalize_organism_name(self.organism)
        
        # Remove from cache if it exists
        if cache_key in self.case_cache:
            del self.case_cache[cache_key]
            print(f"Removed cached case for {self.organism}")
        
        # Generate new case
        return self.generate_case(self.organism)

    def _reset_case_sections(self):
        """Reset all case sections to empty strings."""
        for section in self.case_sections:
            self.case_sections[section] = ""

    def _combine_case_sections(self) -> str:
        """Combine all case sections into a single case document."""
        sections = []
        
        # Add a case title
        sections.append(f"# CLINICAL CASE: {self.organism.upper()} INFECTION")
        sections.append("")
        
        # Add each section with a header
        if self.case_sections["patient_info"]:
            sections.append("## PATIENT INFORMATION")
            sections.append(self.case_sections["patient_info"])
            sections.append("")
        
        if self.case_sections["history_and_exam"]:
            sections.append("## HISTORY AND PHYSICAL EXAMINATION")
            sections.append(self.case_sections["history_and_exam"])
            sections.append("")
        
        if self.case_sections["diagnostics"]:
            sections.append("## DIAGNOSTIC STUDIES")
            sections.append(self.case_sections["diagnostics"])
            sections.append("")
        
        if self.case_sections["diagnosis_and_treatment"]:
            sections.append("## DIAGNOSIS AND TREATMENT")
            sections.append(self.case_sections["diagnosis_and_treatment"])
            sections.append("")
        
        # Join all sections with line breaks
        return "\n".join(sections)

    def _generate_patient_info(self) -> str:
        """Generate the patient information section using RAG."""
        context = self._get_rag_context(f"Patient demographics, risk factors, and common presentations of {self.organism} infections")
        
        prompt = f"""
        Create a realistic patient profile for a case of {self.organism} infection.
        Include:
        - Age, gender, and relevant demographics
        - Significant medical history
        - Risk factors specific to {self.organism} infection
        - Current medications if relevant
        - Social history elements that may be relevant
        
        Medical context:
        {context}
        
        Keep this section concise (200-300 words) but detailed.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["patient_info"] = result
        return result

    def _generate_history_and_exam(self) -> str:
        """Generate the history and physical examination section using RAG."""
        context = self._get_rag_context(f"Clinical presentation, symptoms, and physical examination findings of {self.organism} infections")
        
        # Include patient info as context for consistency
        patient_info = self.case_sections["patient_info"]
        
        prompt = f"""
        Create the history of present illness and physical examination findings for this patient with {self.organism} infection.
        
        Patient information:
        {patient_info}
        
        Include:
        - Presenting complaint and duration
        - Evolution of symptoms
        - Relevant positive and negative findings
        - Vital signs with specific values
        - Detailed physical examination with all relevant systems
        
        Medical context on {self.organism} infections:
        {context}
        
        Keep findings consistent with the patient's profile and the typical presentation of {self.organism}.
        Be specific with values for vital signs and examination findings.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["history_and_exam"] = result
        return result

    def _generate_diagnostics(self) -> str:
        """Generate the diagnostic studies section using RAG."""
        context = self._get_rag_context(f"Laboratory findings, diagnostic tests, and imaging for {self.organism} infections")
        
        # Include previous sections for context
        previous_sections = f"""
        PATIENT INFORMATION:
        {self.case_sections["patient_info"]}
        
        HISTORY AND EXAMINATION:
        {self.case_sections["history_and_exam"]}
        """
        
        prompt = f"""
        Create the diagnostic studies section for this patient with suspected {self.organism} infection.
        
        Previous case information:
        {previous_sections}
        
        Include:
        - Laboratory results with specific values (CBC, chemistry, inflammatory markers)
        - Microbiology results (cultures, Gram stains, molecular tests)
        - Imaging findings if relevant
        - Any other diagnostic tests that would be helpful
        
        Medical context on diagnostic findings in {self.organism} infections:
        {context}
        
        Make the laboratory values and diagnostic findings consistent with the patient's presentation and typical for {self.organism} infection.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["diagnostics"] = result
        return result

    def _generate_diagnosis_and_treatment(self) -> str:
        """Generate the diagnosis and treatment section using RAG."""
        context = self._get_rag_context(f"Diagnosis, treatment, and management of {self.organism} infections")
        
        # Include all previous sections for context
        previous_sections = f"""
        PATIENT INFORMATION:
        {self.case_sections["patient_info"]}
        
        HISTORY AND EXAMINATION:
        {self.case_sections["history_and_exam"]}
        
        DIAGNOSTIC STUDIES:
        {self.case_sections["diagnostics"]}
        """
        
        prompt = f"""
        Create the diagnosis and treatment section for this patient with {self.organism} infection.
        
        Previous case information:
        {previous_sections}
        
        Include:
        - Final diagnosis with specific details (e.g., site of infection, complications)
        - Antimicrobial therapy with specific agents, doses, and durations
        - Additional interventions if needed (surgical, supportive care)
        - Expected prognosis and potential complications
        - Follow-up recommendations
        
        Medical context on treatment of {self.organism} infections:
        {context}
        
        Make the treatment plan evidence-based and appropriate for this specific patient and infection. Include specific antibiotic names, doses, and durations.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["diagnosis_and_treatment"] = result
        return result

    def _get_rag_context(self, query: str) -> str:
        """Get RAG context for a query using Qdrant."""
        # Check if we have cached results for this query
        cache_key = f"{query}_{self.organism}"
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        try:
            # Increment the call counter
            self.qdrant_call_count += 1
            
            # Generate embedding for the query
            embedding_response = self.embedding_client.embeddings.create(
                model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
                input=query
            )
            query_vector = embedding_response.data[0].embedding
            
            # Search for relevant context in Qdrant
            search_results = self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=query_vector,
                limit=5
            )
            
            # Extract and combine text from the search results
            contexts = []
            for result in search_results:
                if "text" in result.payload:
                    contexts.append(result.payload["text"])
            
            # Join contexts with separators
            context_text = "\n---\n".join(contexts)
            
            # Cache the result
            self.context_cache[cache_key] = context_text
            
            return context_text
        except Exception as e:
            print(f"Error retrieving RAG context: {str(e)}")
            return ""

    def _fallback_case_generation(self) -> str:
        """Generate a case without RAG if RAG is not available."""
        print("Using fallback case generation without RAG...")
        self._reset_case_sections()
        
        # Generate each section without RAG
        self._fallback_generate_patient_info()
        self._fallback_generate_history_and_exam()
        self._fallback_generate_diagnostics()
        self._fallback_generate_diagnosis_and_treatment()
        
        # Combine all sections into a complete case
        case_text = self._combine_case_sections()
        
        return case_text

    def _fallback_generate_patient_info(self) -> str:
        """Generate patient info without RAG."""
        prompt = f"""
        Create a realistic patient profile for a case of {self.organism} infection.
        Include age, gender, relevant demographics, medical history, and risk factors.
        Keep this section concise but detailed.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["patient_info"] = result
        return result

    def _fallback_generate_history_and_exam(self) -> str:
        """Generate history and exam without RAG."""
        patient_info = self.case_sections["patient_info"]
        
        prompt = f"""
        Create the history of present illness and physical examination findings for this patient with {self.organism} infection.
        
        Patient information:
        {patient_info}
        
        Include presenting complaint, duration, evolution of symptoms, vital signs, and detailed physical examination.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["history_and_exam"] = result
        return result

    def _fallback_generate_diagnostics(self) -> str:
        """Generate diagnostics without RAG."""
        previous_sections = f"""
        PATIENT INFORMATION:
        {self.case_sections["patient_info"]}
        
        HISTORY AND EXAMINATION:
        {self.case_sections["history_and_exam"]}
        """
        
        prompt = f"""
        Create the diagnostic studies section for this patient with suspected {self.organism} infection.
        
        Previous case information:
        {previous_sections}
        
        Include laboratory results, microbiology results, imaging findings, and other relevant diagnostic tests.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["diagnostics"] = result
        return result

    def _fallback_generate_diagnosis_and_treatment(self) -> str:
        """Generate diagnosis and treatment without RAG."""
        previous_sections = f"""
        PATIENT INFORMATION:
        {self.case_sections["patient_info"]}
        
        HISTORY AND EXAMINATION:
        {self.case_sections["history_and_exam"]}
        
        DIAGNOSTIC STUDIES:
        {self.case_sections["diagnostics"]}
        """
        
        prompt = f"""
        Create the diagnosis and treatment section for this patient with {self.organism} infection.
        
        Previous case information:
        {previous_sections}
        
        Include final diagnosis, antimicrobial therapy, additional interventions, prognosis, and follow-up recommendations.
        """
        
        result = self.generate_response(self.system_prompt, prompt)
        self.case_sections["diagnosis_and_treatment"] = result
        return result 