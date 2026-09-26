from pipeline.acquisition.bhuvan import list_bhuvan_sources


def main():
    sources = list_bhuvan_sources()

    print(f"Found {len(sources)} Bhuvan sources.")

    for source in sources:
        print()
        print("ID:", source["dataset_id"])
        print("Name:", source["name"])
        print("Access:", source["access_type"])
        print("URL:", source["url"])


if __name__ == "__main__":
    main()
