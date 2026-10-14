# 🌱 AgroSmart AI — Smart Farming Assistant

AgroSmart AI is a Python desktop application designed to help farmers explore practical crop-care guidance, ask farming questions, and estimate farm revenue and profit. It includes a built-in farming knowledge base with **English and Tamil** answers and runs its core text-answering and calculator features **without an API key**.

## ✨ Features

- 🌐 **Bilingual Support:** Switch between English and Tamil.
- 🌿 **Crop Disease Guidance:** Describe crop symptoms in text and receive relevant guidance from the built-in knowledge base.
- 🤖 **Smart Farming Advisor:** Ask questions about crops, pests, diseases, irrigation, fertilizers, and farming practices.
- 🎙️ **Voice Input:** Speak farming questions and convert speech into text using optional speech recognition.
- 🧮 **Farm Profit Calculator:** Estimate production, revenue, costs, profit or loss, profit margin, and break-even selling price.
- 📋 **Farming Schemes:** Access government agriculture scheme information included in the application.
- 💻 **Desktop GUI:** A user-friendly interface built with Python Tkinter.
- 📴 **Offline Core Functionality:** Text-based farming guidance and the profit calculator work locally without an API key.

## 🛠️ Technology Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| Tkinter and ttk | Desktop graphical interface |
| difflib | Text and keyword matching |
| SpeechRecognition | Optional speech-to-text |
| sounddevice | Microphone audio capture |
| NumPy | Audio data processing |

## 📋 Requirements

- Python 3.10 or later recommended
- Windows, macOS, or Linux with Tkinter support
- Microphone for voice input
- Internet connection for optional speech recognition

**No API key is required** for the built-in farming knowledge base or profit calculator.

## 🚀 Installation

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_FOLDER>
```

Replace the placeholders with your actual GitHub repository URL and folder name.

### 2. Install dependencies

```bash
python -m pip install SpeechRecognition sounddevice numpy
```

These packages are needed for optional voice input. The text guidance and calculator do not require them.

### 3. Run the application

If your Python file is named `farmo_agrosmart_detailed_knowledge.py`, run:

```bash
python farmo_agrosmart_detailed_knowledge.py
```

If you use another filename, replace the command with that filename.

## 📖 How to Use

1. Launch AgroSmart AI.
2. Select English or Tamil from the language selector.
3. Choose a section from the sidebar:
   - **Dashboard:** View application information and voice-input status.
   - **Crop Disease:** Describe crop symptoms and request guidance.
   - **Crop Analysis:** Ask crop-related questions.
   - **Farming Advisor:** Get guidance through text or voice.
   - **Farm Tools:** Calculate estimated farm revenue and profit.
   - **Schemes:** Read the scheme information included in the knowledge base.
4. For voice input, connect a microphone and click the appropriate Speak button.
5. In Farm Tools, enter your cultivated area, expected yield, selling price, and estimated costs, then click Calculate.

### Example Questions

- Why are my tomato flowers falling?
- What are the common pests in rice?
- How should I manage irrigation for groundnut?
- தக்காளிப் பூக்கள் ஏன் உதிர்கின்றன?
- நெல் பயிரில் ஏற்படும் பொதுவான பூச்சிகள் என்ன?

## 🧮 Farm Profit Calculator

The calculator uses the following formulas:

- **Total production** = Cultivated area × Expected yield per acre
- **Gross revenue** = Total production × Selling price per kg
- **Estimated profit or loss** = Gross revenue − Total estimated costs
- **Profit margin** = Estimated profit ÷ Gross revenue × 100
- **Break-even price per kg** = Total estimated costs ÷ Total production

The results are estimates based on the values entered by the user. They are not guaranteed financial returns or live market prices.

## 🌐 Offline Functionality

AgroSmart AI is designed to provide useful farming guidance without depending on a paid AI API.

- Built-in farming answers work locally.
- The farm profit calculator works locally.
- Optional voice recognition uses Google's speech-recognition service and may require an internet connection.
- Live weather, current market prices, and live government-scheme eligibility are not fetched by the application.

## ⚠️ Disclaimer

AgroSmart AI provides general educational farming information. Its suggestions should not replace field inspection, laboratory diagnosis, or professional agricultural advice.

Crop recommendations may vary according to location, soil conditions, crop variety, and season. Consult your local agriculture department or Krishi Vigyan Kendra (KVK) for region-specific recommendations. Do not apply pesticides based only on an automated text response.

## 🛠️ Troubleshooting

**Application does not start**
- Check Python installation using `python --version`.
- Run the script from the correct project folder.
- Verify that Tkinter is available.

**Microphone is not detected**
- Install the optional voice dependencies.
- Check your operating system's microphone permissions.
- Verify that a working input device is connected.

**Voice recognition fails**
- Check your internet connection.
- Speak clearly and retry.
- Use text input if voice recognition is unavailable.

**Incorrect or irrelevant answer**
- Include the crop name in your question.
- Describe the symptoms more specifically.
- Remember that answers are generated from a built-in knowledge base rather than a general-purpose online AI model.

## 🤝 Contributing

Contributions are welcome!

1. Fork this repository.
2. Create a new branch for your changes.
3. Implement and test your improvements.
4. Submit a pull request describing your changes.

Potential improvements include additional crop information, reviewed Tamil translations, improved accessibility, and automated tests.

## 📄 License

No license has been specified yet. Add a `LICENSE` file before distributing this project under a particular open-source license.

---

**Built with Python to make practical farming guidance more accessible.** 🌾
