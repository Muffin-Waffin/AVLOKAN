from pipeline.acquisition.auth import get_access_token


def main():
    print("Authenticating with Copernicus Data Space...")

    token = get_access_token()

    print("Authentication successful.")
    print(f"Token received: {token[:20]}...")


if __name__ == "__main__":
    main()