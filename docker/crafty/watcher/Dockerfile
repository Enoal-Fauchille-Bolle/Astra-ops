FROM python:3.14-slim

# Install dependencies
RUN pip install requests

# Copy the script
COPY main.py /app/main.py
WORKDIR /app

# Run the proxy
CMD ["python", "-u", "main.py"]
