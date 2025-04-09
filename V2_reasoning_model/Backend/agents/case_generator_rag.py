import os
import json
import time
from typing import Dict, List, Optional
from dotenv import load_dotenv
from .base_agent import BaseAgent
from openai import AzureOpenAI

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
    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        print("Initializing CaseGeneratorRAGAgent...")
        
        # Default organism if none is specified
        self.organism = os.getenv("DEFAULT_ORGANISM", "staphylococcus")
        self.collection = f"{self.organism}_collection"
        
        # System prompt for case generation
        self.system_prompt = """You are an expert medical microbiologist specializing in creating realistic clinical cases.
        Generate detailed, medically accurate cases that include subtle but important diagnostic clues. Each case should be
        challenging but solvable with proper clinical reasoning."""
        
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
        self.embedding_client = AzureOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        )
        
        # Output directory for saving generated cases
        self.output_dir = f"Outputs"
        os.makedirs(self.output_dir, exist_ok=True)
        
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

    def generate_case(self, organism: str = None) -> str:
        """Generate a clinical case for the specified organism."""
        if organism:
            self.organism = organism.lower()
            self.collection = f"{self.organism}_collection"
        
        print(f"Generating case for {self.organism}...")
        
        # Check if case already exists
        case_file = os.path.join(self.output_dir, "case.txt")
        try:
            if os.path.exists(case_file):
                with open(case_file, 'r') as f:
                    case_text = f.read()
                    if self.organism.lower() in case_text.lower():
                        print(f"Found existing case for {self.organism}")
                        return case_text
        except Exception as e:
            print(f"Error checking existing case: {str(e)}")
        
        # Reset case sections
        self._reset_case_sections()
        
        # Reset context cache and call counter
        self.context_cache = {}
        self.qdrant_call_count = 0
        
        # Check if Qdrant is available and working
        if not self.qdrant_client or not HAS_QDRANT:
            print("No Qdrant client available, using fallback case generation")
            return self._fallback_case_generation()
        
        # Try to get context to validate connection
        try:
            test_context = self._get_rag_context(f"Information about {self.organism}")
            if not test_context or len(test_context.strip()) < 20:
                print("Could not retrieve sufficient context, using fallback case generation")
                return self._fallback_case_generation()
            
            print("Successfully retrieved context, proceeding with RAG case generation")
            
            # Generate each section of the case
            self._generate_patient_info()
            self._generate_history_and_exam()
            self._generate_diagnostics()
            self._generate_diagnosis_and_treatment()
            
            # Combine all sections into a complete case
            case_text = self._combine_case_sections()
            
            # Save the case to a file
            with open(case_file, 'w') as f:
                f.write(case_text)
            
            return case_text
            
        except Exception as e:
            print(f"Error in RAG case generation: {str(e)}")
            return self._fallback_case_generation()

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
                model="text-embedding-3-large",
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
        
        # Save the case to a file
        case_file = os.path.join(self.output_dir, "case.txt")
        with open(case_file, 'w') as f:
            f.write(case_text)
        
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