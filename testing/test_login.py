import requests

def test_login():
    url = "https://boseh.uptangkutan-bandung.id/api/user/login"
    
    # Data dari gambar (menggunakan form-data)
    payload = {
        'email': 'admin@mail.com',
        'password': 'thisissuperstrongpassword'
    }
    
    print(f"Mengirim permintaan POST ke: {url}")
    print(f"Payload: {payload}\n")
    
    try:
        # Mengirim POST request dengan form-data
        response = requests.post(url, data=payload)
        
        # Menampilkan status code
        print(f"Status Code: {response.status_code}")
        
        # Mencoba menampilkan response sebagai JSON jika memungkinkan
        try:
            json_response = response.json()
            print("Response JSON:")
            import json
            print(json.dumps(json_response, indent=4))
        except ValueError:
            # Jika bukan JSON, tampilkan teks biasa
            print("Response Text:")
            print(response.text)
            
    except requests.exceptions.RequestException as e:
        print(f"Terjadi kesalahan saat melakukan request: {e}")

if __name__ == "__main__":
    test_login()
