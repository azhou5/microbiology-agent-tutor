import os
from langchain_community.document_loaders import PyPDFLoader

def pdf_to_txt(pdf_folder, txt_folder):
    if not os.path.exists(txt_folder):
        os.makedirs(txt_folder)

    for filename in os.listdir(pdf_folder):
        if filename.endswith('.pdf'):
            file_path = os.path.join(pdf_folder, filename)
            loader = PyPDFLoader(file_path)
            text = ""
            for page in loader.lazy_load():
                text += page.page_content
            txt_filename = os.path.splitext(filename)[0] + '.txt'
            txt_path = os.path.join(txt_folder, txt_filename)
            with open(txt_path, 'w') as txt_file:
                txt_file.write(text)

pdf_folder = './background_info/'
txt_folder = './background_info/'
pdf_to_txt(pdf_folder, txt_folder)

print("All pdf files have been converted to txt files")