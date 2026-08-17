from dotenv import load_dotenv
import uvicorn


def main() -> None:
    load_dotenv()

    print("Docs: http://0.0.0.0:8000/docs\n")

    uvicorn.run(
        "main.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
