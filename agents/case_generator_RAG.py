import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from qdrant_client import QdrantClient
from typing import Dict, List, Any, Optional
from .base_agent import BaseAgent
from agentlite.commons import TaskPackage

# Load environment
load_dotenv('.env')

class CaseGeneratorRAGAgent(BaseAgent):
    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.3):
        super().__init__(model_name, temperature)
        print("Initializing CaseGeneratorRAGAgent...")
        
        # Default organism if none is specified
        self.organism = os.getenv("DEFAULT_ORGANISM", "staphylococcus")
        self.collection = f"{self.organism}_collection"
        
        # System prompt for case generation
        self.system_prompt = """You are an expert medical microbiologist specializing in creating realistic clinical cases.
        Generate detailed, medically accurate cases that include subtle but important diagnostic clues. Each case should be
        challenging but solvable with proper clinical reasoning."""
        
        # Initialize embedding model for RAG
        self.embeddings = AzureOpenAIEmbeddings(model="text-embedding-3-large")
        print(os.getenv("QDRANT_URL"))
        # Initialize Qdrant client
        self.qdrant_client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
        )
        
        # Initialize RAG-specific LLM
        self.rag_llm = AzureChatOpenAI(
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-09-01-preview"),
            temperature=0,
            max_tokens=None,
            timeout=None,
            max_retries=2,
            #model=os.getenv("AZURE_OPENAI_MODEL", "gpt-4o"),
        )
        
        # Initialize chat history
        self.chat_history = [SystemMessage(content=self.system_prompt)]
        
        # Output directory for saving generated cases
        self.output_dir = f"outputs/{self.organism}_case_study"
        
        # Case sections
        self.case_sections = {
            "patient_info": "",
            "history_and_exam": "",
            "diagnostics": "",
            "diagnosis_and_treatment": ""
        }
        
        # Guiding questions for each section
        self.guiding_questions = {
            "patient_info": [],
            "history_and_exam": [],
            "diagnostics": [],
            "diagnosis_and_treatment": []
        }
        
        # Cache for RAG contexts to reduce API calls
        self.context_cache = {}
        
        # Counter for Qdrant API calls
        self.qdrant_call_count = 0

    def __call__(self, task: TaskPackage) -> Dict:
        print("Handling task request...")
        # Extract organism from task if provided
        instruction = task.instruction
        if "organism:" in instruction.lower():
            # Extract organism from instruction
            parts = instruction.lower().split("organism:")
            if len(parts) > 1:
                self.organism = parts[1].strip()
                self.collection = f"{self.organism}_collection"
                self.output_dir = f"outputs/{self.organism}_case_study"
        
        # Generate the case using RAG
        case_text = self.generate_case()
        print("Case generated successfully.")
        
        return {
            "case_text": case_text,
            "case_presentation": "A new case has been generated."
        }

    def generate_case(self) -> str:
        print("Generating a new clinical case...")
        # Reset chat history and case sections
        self.chat_history = [SystemMessage(content=self.system_prompt)]
        self._reset_case_sections()
        self._reset_guiding_questions()
        
        # Reset context cache and call counter
        self.context_cache = {}
        self.qdrant_call_count = 0
        
        try:
            print("Generating condensed sections of the case...")
            # Generate condensed sections of the case
            self._generate_patient_info()  # Includes patient info and chief complaint
            self._generate_history_and_exam()  # Combined history and physical exam
            self._generate_diagnostics()  # Combined labs, imaging, and microbiology
            self._generate_diagnosis_and_treatment()  # Combined diagnosis and treatment
            
            # Generate guiding questions for each section
            for section_name in self.case_sections:
                if self.case_sections[section_name]:
                    self._generate_guiding_questions(section_name)
            
            print("Combining all sections into a complete case...")
            case_text = self._combine_case_sections()
            print("Case combined successfully.")
            
            # Save the case to a file if output directory is set
            self._save_to_file("case.txt", case_text)
            
            # Save individual sections
            for section_name, section_content in self.case_sections.items():
                if section_content:
                    self._save_to_file(f"{section_name}.txt", section_content)
            
            # Save guiding questions for each section
            for section_name, questions in self.guiding_questions.items():
                if questions:
                    questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
                    self._save_to_file(f"{section_name}_questions.txt", questions_text)
            
            print("Logging Qdrant API call statistics...")
            stats = self.get_qdrant_call_stats()
            print(f"Qdrant API call statistics: {stats}")
            
            return case_text
        except Exception as e:
            print(f"Error in RAG case generation: {str(e)}")
            return self._fallback_case_generation()

    def _reset_case_sections(self):
        """Reset all case sections to empty strings."""
        self.case_sections = {
            "patient_info": "",  # Now includes chief complaint
            "history_and_exam": "",  # Combined history and physical exam
            "diagnostics": "",  # Combined labs, imaging, and microbiology
            "diagnosis_and_treatment": ""  # Combined diagnosis and treatment
        }
    
    def _reset_guiding_questions(self):
        """Reset all guiding questions to empty lists."""
        self.guiding_questions = {
            "patient_info": [],
            "history_and_exam": [],
            "diagnostics": [],
            "diagnosis_and_treatment": []
        }

    def _combine_case_sections(self) -> str:
        """Combine all case sections into a single case text."""
        # Format the case in the style of the original implementation
        combined_text = f"""Organism
{self.organism}

Case
"""
        # Add patient info (which now includes chief complaint)
        if self.case_sections["patient_info"]:
            combined_text += self.case_sections["patient_info"] + "\n\n"
        
        # Add history_and_exam
        if self.case_sections["history_and_exam"]:
            combined_text += self.case_sections["history_and_exam"] + "\n\n"
        
        # Add diagnostics
        if self.case_sections["diagnostics"]:
            combined_text += self.case_sections["diagnostics"] + "\n\n"
        
        # Add diagnosis_and_treatment
        if self.case_sections["diagnosis_and_treatment"]:
            combined_text += self.case_sections["diagnosis_and_treatment"] + "\n\n"
        
        # Add guiding questions
        combined_text += "Guiding Questions\n"
        for section, questions in self.guiding_questions.items():
            if questions and len(questions) > 0:
                # Take the first question from each section
                combined_text += f"Question: {questions[0]}\n"
        
        # Generate key concepts
        key_concepts = self._generate_key_concepts()
        combined_text += f"\nKey Concepts\n{key_concepts}"
        
        return combined_text

    def _generate_patient_info(self) -> str:
        """Generate patient demographic information and chief complaint."""
        print("Generating patient info and chief complaint...")
        prompt = f"""
        Generate patient demographic information AND chief complaint for a case involving {self.organism} infection.
        
        PART 1: PATIENT INFO
        Include age, gender, occupation, and any relevant background information.
        
        PART 2: CHIEF COMPLAINT
        Include the main reason for seeking medical attention and the duration of symptoms.
        Make sure the symptoms are consistent with {self.organism} infection.
        
        Format as a cohesive paragraph without headings, starting with demographic information and 
        flowing naturally into the chief complaint.
        
        Example:
        "Mr. Smith is a 45-year-old male who works as a high school teacher with a history of well-controlled 
        type 2 diabetes. He presents to the emergency department with a 3-day history of fever, productive 
        cough with yellow sputum, and right-sided chest pain that worsens with deep breathing. He reports 
        feeling increasingly short of breath over the past 24 hours."
        """
        return self._generate_section("patient_info", prompt)

    def _generate_history_and_exam(self) -> str:
        """Generate combined medical history and physical examination."""
        print("Generating combined history and physical examination...")
        prompt = f"""
        Generate a COMBINED medical history AND physical examination for a patient with {self.organism} infection.
        
        PART 1: MEDICAL HISTORY
        Include past medical history, medications, allergies, social history, and any relevant epidemiological factors.
        Make sure the history includes risk factors relevant to {self.organism} infection.
        
        PART 2: PHYSICAL EXAMINATION
        Include vital signs and detailed examination findings relevant to the infection.
        Make sure the findings are consistent with {self.organism} infection.
        
        Format as a cohesive narrative without headings, starting with the history and 
        flowing naturally into the physical examination findings.
        
        Example:
        "The patient has a history of alcoholic cirrhosis with two exacerbations in the past year. 
        Current medications include fluticasone/salmeterol inhaler and lisinopril. He has a 30 pack-year 
        smoking history. On examination, the patient appears acutely ill with temperature 103°F, 
        blood pressure 100/60 mmHg, heart rate 120 bpm, respiratory rate 20 breaths per minute, 
        and oxygen saturation 93% on room air. Chest examination revealed bronchial breath sounds 
        and egophony on the right. His cough was productive of thick green sputum."
        """
        return self._generate_section("history_and_exam", prompt)

    def _generate_diagnostics(self) -> str:
        """Generate combined laboratory, imaging, and microbiology findings."""
        print("Generating combined diagnostics (labs, imaging, microbiology)...")
        prompt = f"""
        Generate COMBINED diagnostic findings including laboratory tests, imaging studies, and microbiology 
        results for a patient with {self.organism} infection.
        
        PART 1: LABORATORY FINDINGS
        Include complete blood count, basic metabolic panel, inflammatory markers, and other relevant tests.
        
        PART 2: IMAGING FINDINGS
        Include relevant imaging studies such as X-rays, CT scans, or other appropriate imaging.
        
        PART 3: MICROBIOLOGY FINDINGS
        Include results of cultures, Gram stains, molecular tests that explicitly identify {self.organism}.
        Include antimicrobial susceptibility results.
        
        Format as a cohesive narrative without headings, organizing the information logically from 
        initial lab tests to imaging to microbiological confirmation.
        
        Example:
        "Laboratory studies reveal: WBC 15,000/μL with 85% neutrophils, Hgb 8 g/dL, platelets 250,000/μL, 
        and elevated C-reactive protein at 15 mg/dL. Chest X-ray shows lobar consolidation in the right 
        lower lobe with a small pleural effusion. Sputum Gram stain shows numerous neutrophils and 
        gram-positive diplococci. Cultures from both sputum and blood (2/2 sets) grow Streptococcus 
        pneumoniae sensitive to penicillin, ceftriaxone, and levofloxacin."
        """
        return self._generate_section("diagnostics", prompt)

    def _generate_diagnosis_and_treatment(self) -> str:
        """Generate combined diagnosis and treatment plan."""
        print("Generating combined diagnosis and treatment plan...")
        prompt = f"""
        Generate a COMBINED final diagnosis AND treatment plan for a patient with {self.organism} infection.
        
        PART 1: DIAGNOSIS
        Clearly state that the patient has an infection caused by {self.organism}.
        Include the specific type of infection (e.g., pneumonia, meningitis, etc.).
        
        PART 2: TREATMENT PLAN
        Include appropriate antimicrobial therapy, supportive care, and any other relevant interventions.
        Include route, dose, and duration of therapy where appropriate.
        Include monitoring requirements and follow-up recommendations.
        
        Format as a cohesive narrative without headings, starting with the diagnosis and 
        flowing naturally into the treatment plan.
        
        Example:
        "The patient is diagnosed with community-acquired pneumonia caused by Streptococcus pneumoniae, 
        complicated by bacteremia. The diagnosis is supported by the clinical presentation, radiographic 
        findings, and positive cultures. The patient is started on intravenous ceftriaxone 2g daily and 
        azithromycin 500mg daily with supplemental oxygen to maintain saturation above 92%. Given the 
        bacteremia, a 14-day course of antibiotics is planned with transition to oral antibiotics once 
        clinically improved and afebrile for 48 hours."
        """
        return self._generate_section("diagnosis_and_treatment", prompt)

    def _generate_section(self, section_name: str, prompt: str) -> str:
        """Generate content for a specific section using RAG."""
        print(f"Generating {section_name} section...")
        try:
            # Use cached context instead of making a new API call
            context_key = f"{section_name}_{self.organism}"
            if context_key not in self.context_cache:
                self.context_cache[context_key] = self._get_rag_context(f"Information about {self.organism} related to {section_name}")
            
            context = self.context_cache[context_key]
            
            # Add context to the prompt
            rag_prompt = f"""
            {prompt}
            
            Use the following medical context about {self.organism} to inform your response:
            {context}
            
            Generate a detailed, medically accurate response.
            """
            
            # Generate content using the RAG LLM
            self.chat_history.append(HumanMessage(content=rag_prompt))
            result = self.rag_llm.invoke(self.chat_history)
            self.chat_history.append(AIMessage(content=result.content))
            
            # Store the generated content
            content = result.content.strip()
            self.case_sections[section_name] = content
            
            # Save section to file
            self._save_to_file(f"{section_name}.txt", content)
            
            return content
        except Exception as e:
            print(f"Error generating {section_name} section: {str(e)}")
            # Fall back to non-RAG generation
            return self._fallback_generate_section(prompt)

    def _get_rag_context(self, query: str) -> str:
        print(f"Retrieving RAG context for query: {query}...")
        try:
            # Increment the call counter
            self.qdrant_call_count += 1
            
            embedded_query = self.embeddings.embed_query(query)
            
            # Retrieve top matches in Qdrant database
            search_results = self.qdrant_client.search(
                collection_name=self.collection,
                query_vector=embedded_query,
                limit=5,  # Number of results
                with_payload=True
            )
            
            context = ""
            for item in search_results:
                context += item.payload.get('text', '')
            
            return context
        except Exception as e:
            print(f"Error retrieving RAG context: {str(e)}")
            return ""

    def get_qdrant_call_stats(self) -> Dict:
        """Return statistics about Qdrant API calls."""
        return {
            "total_calls": self.qdrant_call_count,
            "cached_contexts": len(self.context_cache),
            "cache_keys": list(self.context_cache.keys())
        }

    def _fallback_case_generation(self) -> str:
        print("Fallback case generation initiated...")
        # Reset case sections
        self._reset_case_sections()
        self._reset_guiding_questions()
        
        # Reset context cache
        self.context_cache = {}
        
        try:
            # Generate each section without RAG
            self.case_sections["patient_info"] = self._fallback_generate_section(
                "Generate patient demographic information AND chief complaint for a clinical case involving a microbial infection."
            )
            self.case_sections["history_and_exam"] = self._fallback_generate_section(
                "Generate COMBINED medical history AND physical examination for a patient with a microbial infection."
            )
            self.case_sections["diagnostics"] = self._fallback_generate_section(
                "Generate COMBINED laboratory, imaging, and microbiology findings for a patient with a microbial infection."
            )
            self.case_sections["diagnosis_and_treatment"] = self._fallback_generate_section(
                "Generate COMBINED diagnosis AND treatment plan for a patient with a microbial infection."
            )
            
            # Generate fallback guiding questions for each section
            for section_name in self.case_sections:
                if self.case_sections[section_name]:
                    self._fallback_generate_guiding_questions(section_name)
            
            # Combine all sections into a complete case
            return self._combine_case_sections()
        except Exception as e:
            print(f"Error in fallback case generation: {str(e)}")
            
            # Return a very basic fallback case if everything fails
            return """A 45-year-old male presents with fever and productive cough for 3 days. Temperature is 38.5°C, blood pressure 120/80, heart rate 88, respiratory rate 20. Examination reveals crackles in the right lung base. Previously healthy, working as an office worker. Several coworkers have had similar symptoms. Laboratory studies show elevated white blood cell count with neutrophil predominance. Chest X-ray reveals right lower lobe infiltrate. Sputum culture grows Streptococcus pneumoniae."""

    def _fallback_generate_section(self, prompt: str) -> str:
        """Generate a section using the standard LLM approach if RAG fails."""
        try:
            response = self.llm_layer(prompt)
            
            # Ensure we got a valid response
            if isinstance(response, str) and len(response) > 10:  # Basic validation
                return response.strip()
            return ""
        except Exception as e:
            print(f"Error in fallback section generation: {str(e)}")
            return ""
    
    def _fallback_generate_guiding_questions(self, section_name: str) -> List[str]:
        """Generate guiding questions using the standard LLM approach if RAG fails."""
        try:
            section_content = self.case_sections[section_name]
            
            # Skip if section is empty
            if not section_content:
                return []
            
            prompt = f"""
            Based on the following case section about a patient with a microbial infection, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts from this case.
            
            The questions should:
            1. Highlight important diagnostic or therapeutic considerations
            2. Encourage critical thinking about the pathophysiology
            3. Connect clinical findings to microbiology concepts
            4. Challenge students to apply their knowledge
            
            Case Section ({section_name}):
            {section_content}
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
            
            response = self.llm_layer(prompt)
            
            # Parse questions from the response
            questions = []
            for line in response.strip().split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('•')):
                    # Remove number/bullet and clean up
                    question = line.split('.', 1)[-1].strip() if '.' in line else line.split('•', 1)[-1].strip()
                    questions.append(question)
            
            # Store the questions
            self.guiding_questions[section_name] = questions
            
            return questions
        except Exception as e:
            print(f"Error in fallback guiding questions generation: {str(e)}")
            return []

    def _save_to_file(self, filename: str, content: str):
        print(f"Saving content to file: {filename}...")
        try:
            os.makedirs(self.output_dir, exist_ok=True)
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, "w") as f:
                f.write(content)
        except Exception as e:
            print(f"Error saving to file: {str(e)}")

    def reset(self):
        """Reset the agent state."""
        self.chat_history = [SystemMessage(content=self.system_prompt)]
        self._reset_case_sections()
        self._reset_guiding_questions()
        self.context_cache = {}
        self.qdrant_call_count = 0

    def _generate_guiding_questions(self, section_name: str) -> List[str]:
        """Generate guiding questions for a specific section based on its content and RAG context."""
        section_content = self.case_sections[section_name]
        
        # Skip if section is empty
        if not section_content:
            return []
        
        # Use cached context instead of making a new API call
        context_key = f"{section_name}_{self.organism}"
        if context_key not in self.context_cache:
            # If not in cache (shouldn't happen normally), get it
            self.context_cache[context_key] = self._get_rag_context(f"Information about {self.organism} related to {section_name}")
        
        context = self.context_cache[context_key]
        
        # Create prompt for generating guiding questions based on section type
        if section_name == "patient_info":
            prompt = f"""
            Based on the following patient information about a case with {self.organism} infection and the provided medical context, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts.
            
            The questions should:
            1. Highlight important host factors that may predispose to this infection
            2. Encourage critical thinking about risk factors
            3. Connect patient demographics to epidemiology of {self.organism}
            4. Challenge students to consider how patient factors influence clinical presentation and management
            
            Case Section (Patient Information):
            {section_content}
            
            Medical Context:
            {context}
            
            Example question format from a Streptococcus pneumoniae case:
            "What are the notable characteristics of the host that increase risk for this infection?"
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
        elif section_name == "history_and_exam":
            prompt = f"""
            Based on the following medical history for a patient with {self.organism} infection and the provided medical context, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts.
            
            The questions should:
            1. Focus on risk factors specific to {self.organism} infection
            2. Encourage critical thinking about epidemiological factors
            3. Challenge students to connect medical history to susceptibility
            4. Consider preventive measures that might have been appropriate
            
            Case Section (History):
            {section_content}
            
            Medical Context:
            {context}
            
            Example question format from a Streptococcus pneumoniae case:
            "How does the patient's history of alcoholic cirrhosis affect their risk for this infection?"
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
        elif section_name == "diagnostics":
            prompt = f"""
            Based on the following laboratory findings for a patient with {self.organism} infection and the provided medical context, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts.
            
            The questions should:
            1. Focus on characteristic laboratory abnormalities in {self.organism} infection
            2. Encourage critical thinking about the pathophysiology behind these abnormalities
            3. Challenge students to interpret the significance of specific values
            4. Consider how laboratory findings guide management decisions
            
            Case Section (Labs):
            {section_content}
            
            Medical Context:
            {context}
            
            Example question format from a Streptococcus pneumoniae case:
            "What do you think is the cause of the elevated creatinine? How about the hyperbilirubinemia?"
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
        elif section_name == "diagnosis_and_treatment":
            prompt = f"""
            Based on the following diagnosis for a patient with {self.organism} infection and the provided medical context, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts.
            
            The questions should:
            1. Focus on diagnostic criteria for {self.organism} infection
            2. Encourage critical thinking about differential diagnosis
            3. Challenge students to consider complications and their management
            4. Consider the certainty of diagnosis and what additional information might be helpful
            
            Case Section (Diagnosis):
            {section_content}
            
            Medical Context:
            {context}
            
            Example question format:
            "What clinical, laboratory, and microbiological findings support this diagnosis?"
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
        else:
            prompt = f"""
            Based on the following case section about a patient with {self.organism} infection and the provided medical context, 
            generate 3-5 thought-provoking questions that would help medical students learn key concepts from this case.
            
            The questions should:
            1. Highlight important diagnostic or therapeutic considerations
            2. Encourage critical thinking about the pathophysiology
            3. Connect clinical findings to microbiology concepts
            4. Challenge students to apply their knowledge
            5. Focus on aspects unique to {self.organism} infections
            
            Case Section ({section_name}):
            {section_content}
            
            Medical Context:
            {context}
            
            Generate only the questions, numbered 1-5, without explanations or answers.
            """
        
        try:
            # Generate questions using the RAG LLM
            self.chat_history.append(HumanMessage(content=prompt))
            result = self.rag_llm.invoke(self.chat_history)
            self.chat_history.append(AIMessage(content=result.content))
            
            # Parse questions from the response
            questions = []
            for line in result.content.strip().split('\n'):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith('•')):
                    # Remove number/bullet and clean up
                    question = line.split('.', 1)[-1].strip() if '.' in line else line.split('•', 1)[-1].strip()
                    questions.append(question)
            
            # Store the questions
            self.guiding_questions[section_name] = questions
            
            # Save guiding questions to file if they exist
            if questions:
                questions_text = "\n\n".join([f"Question: {q}" for q in questions])
                self._save_to_file(f"{section_name}_questions.txt", questions_text)
            
            return questions
        except Exception as e:
            print(f"Error generating guiding questions for {section_name}: {str(e)}")
            return []

    def _generate_key_concepts(self) -> str:
        """Generate key concepts for the case based on the generated content."""
        print("Generating key concepts...")
        try:
            # Combine all sections for context
            all_content = "\n\n".join([
                f"{section_name.upper()}:\n{content}" 
                for section_name, content in self.case_sections.items() 
                if content
            ])
            
            # Use cached context for the organism
            context_key = f"key_concepts_{self.organism}"
            if context_key not in self.context_cache:
                self.context_cache[context_key] = self._get_rag_context(f"Key concepts about {self.organism} infections")
            
            context = self.context_cache[context_key]
            
            prompt = f"""
            Based on the following case about a patient with {self.organism} infection, 
            generate 5-7 key concepts that medical students should learn from this case.
            
            The key concepts should:
            1. Focus on important microbiological characteristics of {self.organism}
            2. Highlight pathophysiology of the infection
            3. Emphasize diagnostic approaches
            4. Include treatment principles
            5. Cover prevention strategies if applicable
            
            Case Content:
            {all_content}
            
            Medical Context about {self.organism}:
            {context}
            
            Format each key concept as a brief bullet point (1-2 sentences).
            """
            
            # Generate key concepts using the RAG LLM
            self.chat_history.append(HumanMessage(content=prompt))
            result = self.rag_llm.invoke(self.chat_history)
            self.chat_history.append(AIMessage(content=result.content))
            
            # Save key concepts to file
            key_concepts = result.content.strip()
            self._save_to_file("key_concepts.txt", key_concepts)
            
            return key_concepts
        except Exception as e:
            print(f"Error generating key concepts: {str(e)}")
            return self._fallback_generate_key_concepts()
    
    def _fallback_generate_key_concepts(self) -> str:
        """Generate key concepts without RAG if the RAG approach fails."""
        try:
            # Combine all sections for context
            all_content = "\n\n".join([
                f"{section_name.upper()}:\n{content}" 
                for section_name, content in self.case_sections.items() 
                if content
            ])
            
            prompt = f"""
            Based on the following case about a patient with a microbial infection, 
            generate 5-7 key concepts that medical students should learn from this case.
            
            Case Content:
            {all_content}
            
            Format each key concept as a brief bullet point (1-2 sentences).
            """
            
            response = self.llm_layer(prompt)
            return response.strip()
        except Exception as e:
            print(f"Error in fallback key concepts generation: {str(e)}")
            return "• Importance of early diagnosis and appropriate antimicrobial therapy\n• Recognition of characteristic clinical presentations\n• Understanding of risk factors for infection\n• Proper specimen collection and interpretation of laboratory results\n• Principles of antimicrobial stewardship"