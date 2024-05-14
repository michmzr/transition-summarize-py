from fastapi import FastAPI
from langchain_community.document_loaders import YoutubeAudioLoader
from langchain_community.document_loaders.generic import GenericLoader
from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal, OpenAIWhisperParser
import static_ffmpeg

app = FastAPI()

static_ffmpeg.add_paths()

@app.get("/")
async def root():
    print("downloading...")


    # inspiration: https://python.langchain.com/docs/integrations/document_loaders/youtube_audio/
    # Two Karpathy lecture videos
    urls = ["https://youtu.be/kCc8FmEb1nY"]

    # Directory to save audio files
    save_dir = "./downloads/YouTube"

    # set a flag to switch between local and remote parsing
    # change this to True if you want to use local parsing
    local = False

    # Transcribe the videos to text
    if local:
        loader = GenericLoader(
            YoutubeAudioLoader(urls, save_dir), OpenAIWhisperParserLocal()
        )
    else:
        loader = GenericLoader(YoutubeAudioLoader(urls, save_dir), OpenAIWhisperParser())
    docs = loader.load()
    print("Ready!!!")
    print(docs[0].page_content[0:500])

    return {"message": "Hello World"}


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}
