import fitz

def test_pdf(file_path):
    print(f"Testing {file_path}")
    try:
        doc = fitz.open(file_path)
        for i in range(len(doc)):
            page = doc[i]
            images = page.get_images()
            print(f"Page {i}: {len(images)} images found")
            for img in images:
                print(f"Image: {img}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_pdf(r"C:\Users\BertWu\Desktop\TaxSlip\2025\RBC_T4.pdf")
    test_pdf(r"C:\Users\BertWu\Desktop\TaxSlip\2025\InterCiti_T4_2025.pdf")
