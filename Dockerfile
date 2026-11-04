FROM python:3.11-slim

# Copy application source
COPY ./source ./source

# Copy requirements.txt
COPY ./requirements.txt ./requirements.txt

# Install python dependencies
RUN pip install -r ./requirements.txt

# run the python app
CMD ["python", "source/telegram_bot.py"]
