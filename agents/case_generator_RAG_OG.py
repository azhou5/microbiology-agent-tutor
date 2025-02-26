import os
from dotenv import load_dotenv
from langchain_openai import AzureChatOpenAI
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from qdrant_client import QdrantClient

ORGANISM = "nocardia"
COLLECTION = f"{ORGANISM}_collection"

# Load environment
load_dotenv('../env.dev')

# Initialize embedding model for embedding queries
embeddings = AzureOpenAIEmbeddings(model="text-embedding-3-large")

# Initialize Qdrant client - points to the unique cluster (microbiology-case-gen)
qdrant_client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
)

# Initialize LLM model for generating case
llm = AzureChatOpenAI(
    azure_deployment='gpt-35-turbo-16k',  # or your deployment
    api_version="2024-09-01-preview",  # or your api version
    temperature=0,
    max_tokens=None,
    timeout=None,
    max_retries=2,
    model="gpt-3.5-turbo",
)

# Set file path for outputs
output_dir = f"../{ORGANISM}_case_study_outputs"

def save_to_file(filename, content):
    """
    Save content to a file named ../{ORGANISM}_case_study_outputs/filename.
    """
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(content)

# Initialize LLM chat history with system message
system_message = "You are an AI assistant that generates detailed, unique medical cases for a microbiology class exercise for medical school students."
chat_history = [SystemMessage(content=system_message)]

def generate_case_section(input_text, file_suffix):
    """
    Generate content for a specific case section, save it to a file, and update chat history.
    """
    
    embedded_query = embeddings.embed_query(input_text)
    
    # Retrieve top matches in Qdrant database
    search_results = qdrant_client.search(
        collection_name=COLLECTION,
        query_vector=embedded_query,
        limit=5,  # Number of results
        with_payload=True
    )

    context = ""
    for item in search_results:
        context += item.payload['text']

    augmented_prompt = f"""
    You are a helpful assistant. Use the following pieces of context to answer the question at the end.

    If you don't know the answer, just say that you don't know. DO NOT try to make up an answer.

    {context}

    Question: {input_text}
    Helpful Answer:
    """

    chat_history.append(HumanMessage(content=augmented_prompt))

    result = llm.invoke(chat_history)

    chat_history.append(AIMessage(content = result.content))
    save_to_file(f"{ORGANISM}_{file_suffix}.txt", result.content)


# Case section
case_input = f"""
Your task is to generate a detailed, unique medical case for a patient suffering from an infection with {ORGANISM}. 
You will be provided with background information from a textbook on {ORGANISM}.
Your response should include five sections: organism, case, summary of case, guiding questions, and key concepts.
The case should include unique details that may not be true of every patient with a {ORGANISM} infection. 
It should also include results of a physical exam, like body temperature, heart rate, blood pressure, respiratory rate, SpO2, and results of lab studies and relevant examinations.
The summary of case should be a one-sentence summary of the patient that reveals very few details.
Here is an example case for a different organism:
<example case>
Organism
Strep pneumoniae

Case
A 70 y/o man with alcoholic cirrhosis developed coryza (runny nose) and a mild cough. He 
thought he had a cold. However, four days later at 11PM he had an abrupt onset of shaking chills 
and a fever of 103°F. He thought he could "shake off" the illness with rest but the next day he felt
much weaker and remained feverish. When asked, he said he spent some time with a friend who 
was coughing. The cough was persistent and the right side of his chest hurt when he coughed or took a deep 
breath. When he noticed blood streaking in his sputum he became alarmed and called his 
daughter who took him to the hospital. On physical exam, he is ill-appearing. 103°F, HR 120, BP
100/60, RR 20, SpO2 93% on RA. Chest examination revealed bronchial breath sounds and 
egophony on the right. His cough was productive of thick green sputum. Chest X ray shows lobar
consolidation and opacification, and multifocal opacities. Lab studies reveal elevated creatinine, 
elevated liver enzymes, elevated WBCs. The individual also is anemic, with an Hgb of 8, low 
serum albumin, increased LDH, an indirect hyperbilirubinemia, and elevated CRP and 
procalcitonin.

Summary of Case
A 70 y/o man with alcoholic cirrhosis presents at the hospital with a persistent cough with thick green sputum, and a fever.

Guiding Questions
Question: What are the notable characteristics of the host?
Answer:
- Age 70, immune senescence function putting individuals at higher risk for 
infection
- Alcohol use leading to decreased neutrophil function and increased risk for 
aspiration pneumonia
- Cirrhosis associated immune dysfunction, alterations in gut barrier and proinflammatory response
Question: What do you think is the cause of the elevated creatinine? How about the hyperbilirubinemia?

Key Concepts
- There is significant interaction between the host and the environment that predisposes 
them to a bacterial pneumonia. Some of these include the history of alcohol use causing a
weakened immune system.
- Lab findings reveal a systemic inflammatory response, as well as signs of end organ 
damage.
- Cough produces thick green sputum, which is indicatory of a bacterial pneumonia.
- X ray shows lobar consolidation.
- Physical exam reveals signs of respiratory distress (93% SpO2 on RA), and infection 
(fever to 103).
- High fever with shaking chills
- Productive cough with scant hemoptysis
- Focal pleuritic chest pain with focal consolidation is concerning for bacterial pneumonia.
- Anemia can occur
- Sepsis is possible and 25% of patients hospitalized have pathogen in the blood.
</example case>

Your generated case should have the same level of detail as the example case.
Your output:
"""
generate_case_section(case_input, "case")

# Pathophysiology section
pathophysiology_input = f"""
Now, generate pathophysiology information for this case.
You will be provided with background information from a textbook on {ORGANISM}.

Here is an example case for a different organism:
<example>
Pathophysiology
- Streptococcus pneumoniae commonly colonizes the nasopharynx. It can descend into the 
lungs, especially following a disruption in normal respiratory defenses, such as after a 
viral infection.
- Major virulence factors are Capsular polysaccharides and IgA1 protease
- The capsule can cause immune evasion.
- There are two available vaccines against Strep pneumoniae: PCV13/15 and PPSV23. 
These target the polysaccharide capsule.

Key concepts
The major virulence factors are the capsular polysaccharides.
</example>

Your output:
"""
generate_case_section(pathophysiology_input, "pathophysiology")

# Epidemiology section
epidemiology_input = f"""
Now, generate epidemiology information for this case.
You will be provided with background information from a textbook on {ORGANISM}.
Here is an example case for a different organism:
<example>
Epidemiology/Clinical Reasoning
Given the presence of green sputum, a bacterial etiology is most likely. Strep pneumoniae is the 
most common organism that causes bacterial pneumonia. However, viral etiologies are more 
common overall (rhinovirus, influenza, RSV, coronavirus). Other bacterial pneumonia include S 
aureus.

Guiding Question
What are the most common organisms that cause a similar presentation? How do the clinical 
features change your ranking of these organisms?

Key concepts
- Viral pneumonias are more common than bacterial pneumonias.
- But, in this case, bacterial pneumonias are more likely due to clinical features (green 
sputum).
</example>

Your output for f{ORGANISM}:
"""
generate_case_section(epidemiology_input, "epidemiology")

# Diagnostic section
diagnostic_input = f"""
Now, generate differential diagnostic information for this {ORGANISM} case.
You will be provided with background information from a textbook on {ORGANISM}.
Here is an example case for a different organism:
<example>
Differential Diagnosis
Streptococcus pneumoniae, Staphylococcus aureus, Mycoplasma pneumoniae, COVID19, influenza, Lung cancer.

Additional Diagnostics
Most of the clinical diagnostics have already been conducted, including the chest x-ray, laboratories.
Culture of the pathogen is the best way to diagnose a bacterial pneumonia and the go-to method. 
• Growth in sputum culture and a positive Gram stain is sufficient to make the diagnosis
COVID tests and flu tests will rule out these common viral etiologies.
Streptococcus urinary antigen may also be used, with a sensitivity of ~75%, specificity of 95%, 
PPV of 79%. This test can remain positive for weeks and is not useful in children due to heavy 
pharyngeal colonization.
Biofire Pneumonia panel. Detects 33 targetes including many community acquired and nocosomial bacteria.
Blood cultures are present in 20-25% of patients with pneumonia.

Key concepts:
- The go-to diagnostic is sputum culture and gram stain, which is sufficient for a diagnostic.
- There are a variety of other diagnostic tests that can detect less common pathogens including the 
Biofire pneumonia panel.
</example>

Your differential diagnostic information should have the same level of detail or more as the example.
Your output for {ORGANISM}:
"""
generate_case_section(diagnostic_input, "diagnostics")

# Treatment section
treatment_input = f"""
Now, generate treatment information for this {ORGANISM} case.
You will be provided with background information from a textbook on {ORGANISM}.
Your response should include three sections: treatment, guiding questions, and key concepts.
Here is an example case for a different organism:
<example>
Treatment
- Start with broad-spectrum antibiotics to cover common pathogens like Streptococcus pneumoniae.
- Beta-lactams (e.g., ceftriaxone or amoxicillin-clavulanate).
- Macrolides (e.g., azithromycin) or doxycycline may be added to cover atypical organisms.
- Administer oxygen if hypoxemic.
- Ensure adequate hydration and electrolyte balance.
- Continue monitoring vital signs and oxygen saturation.
- Regularly monitor liver function, kidney function, and electrolytes.
- Chest X-ray to assess progression or resolution

Guiding questions:
- Before the culture results are out, how should you manage the patient? 
- After the culture results are, how will you modify this plan?

Key concepts:
- Manage with beta-lactams to empirically cover pathogens including strep pneumonia. 
- Cover other organisms with macrolides until culture results are returned.
- Initiate supportive care.
</example>

Your treatment information should have the same level of detail or more as the example.
Your output for {ORGANISM}:
"""
generate_case_section(treatment_input, "treatment")

print(f"Case study for {ORGANISM} saved in {output_dir}.")