from flask import Flask, request

app = Flask(__name__)

@app.route('/logistics/dispatch', methods=['POST'])
def receive_data():
    data = request.json
    print("\n" + "="*50)
    print(f" MOCK SERVER RECEIVED DATA!")
    print(f" Payload Data: {data}")
    print("="*50 + "\n")
    return {"status": "success", "message": "Truck dispatch triggered by AI"}, 200

if __name__ == '__main__':
    # Running on port 8000
    app.run(port=8000)