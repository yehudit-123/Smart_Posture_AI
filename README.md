python -m venv venv
venv\Scripts\activate
pip install -r requirements_light.txt
pip install -r requirements_heavy.txt
python main_light.py
python main.py
