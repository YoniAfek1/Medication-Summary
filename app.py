import re
from io import BytesIO
from flask import Flask, request, send_file, render_template, jsonify
from PyPDF2 import PdfReader

app = Flask(__name__)

# 1. Your category → list of full entries
DRUG_CATEGORIES = {
    "Weak opioids": [
        "ROKACET PLUS",
        "ZALDIAR",
        "TRAMADEX - TRAMADOL - Tramal",
        "BUTRANS - BUPERNORPHINE"
    ],
    "Strong opioids": [
        "PERCOCET - OXYCODONE",
        "TARGIN - OXYCODONE",
        "OXYCONTIN – OXYCODONE",
        "OXYCOD SYRUP",
        "FENTANYL - fenta- fentadol",
        "MORPHINE - MCR - M.C.R - MIR - M.I.R"
    ],
    "Adjuvants / anti neuropathic pain": [
        "LYRICA - PREGABALIN",
        "GABAPENTIN - neurontin",
        "CYMBALTA - DULOXETINE - dulox",
        "VENLAFAXINE - VIEPAX - venla",
        "ELATROL - AMITRIPTYLINE - elatrolet",
        "NORTYLIN - NORTRIPTYLINE",
        "IXEL - MILNACIPRAN",
        "TEGRETOL - CARBAMAZEPINE - teril -",
        "TRILEPTIN – OXCARBAZEPINE - trileptal - trexapin - timonil- carbi "
    ],
    "Muscle relaxants": [
        "MUSCOL",
        "BACLOSAL – BACLOFEN",
        "DANTRIUM – DANTROLENE"
    ]
}

# 2. Build a synonym → [(category, full_entry), …] map
SYNONYM_MAP = {}
for cat, entries in DRUG_CATEGORIES.items():
    for entry in entries:
        # split on hyphen to get each "word" that may appear by itself
        parts = [p.strip() for p in entry.upper().split("-")]
        for synonym in parts:
            SYNONYM_MAP.setdefault(synonym, []).append((cat, entry))

def sanitize(line: str) -> str:
    """Replace all non-letter characters with spaces."""
    return re.sub(r'[^A-Za-z]', ' ', line)

def find_drugs_in_pdf(pdf_stream):
    """Find matches of drug names in the PDF, with special logic for NSAIDS, COXI."""
    reader = PdfReader(pdf_stream)
    results = {cat: [] for cat in DRUG_CATEGORIES}
    
    # NSAIDS, COXI updated term list
    nsaids_terms = [
        "ARCOXIA", "ETORICOXIB", "CELCOX", "CELECOXIB", "IBUPROFEN", "NUROFEN", "COMBODEX", "Advil",
        "Etopan", "Etodalac", "Voltaren", "Abitren", "Diclofenac", "brexin", "indomethacin", "naxin",
        "naproxen", "piroxicam", "point"
    ]
    nsaids_terms = [t.lower() for t in nsaids_terms]
    nsaids_found = False

    # Extract all text from the PDF
    full_text = ""
    for page in reader.pages:
        full_text += (page.extract_text() or "") + "\n"
    
    # Sanitize and normalize the full text to lowercase
    sanitized_text = sanitize(full_text).lower()

    # Special logic for NSAIDS, COXI
    for term in nsaids_terms:
        pattern = rf'\b{re.escape(term)}\b'
        if re.search(pattern, sanitized_text):
            nsaids_found = True
            break
    if nsaids_found:
        results["NSAIDS, COXI"] = ["NSAIDS, COXI"]
    else:
        results["NSAIDS, COXI"] = []

    # All other categories as before
    for category, drug_entries in DRUG_CATEGORIES.items():
        if category == "NSAIDS, COXI":
            continue
        for drug_entry in drug_entries:
            synonyms = [s.strip().lower() for s in re.split(r'[-–]', drug_entry)]
            for synonym in synonyms:
                if not synonym:
                    continue
                if len(synonym) >= 5:
                    if synonym in sanitized_text:
                        if drug_entry not in results[category]:
                            results[category].append(drug_entry)
                        break
                else:
                    pattern = rf'\b{re.escape(synonym)}\b'
                    if re.search(pattern, sanitized_text):
                        if drug_entry not in results[category]:
                            results[category].append(drug_entry)
                        break
    # Fixed output order
    output_order = [
        "NSAIDS, COXI",
        "Weak opioids",
        "Strong opioids",
        "Adjuvants / anti neuropathic pain",
        "Muscle relaxants"
    ]
    ordered_results = {cat: results[cat] for cat in output_order if results[cat]}
    return ordered_results

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'pdf_file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['pdf_file']
    if not file or not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Invalid file type'}), 400
    
    try:
        results = find_drugs_in_pdf(file.stream)
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000) 