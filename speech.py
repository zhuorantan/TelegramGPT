import aiohttp

class SpeechClient:
  def __init__(self, key: str, region: str = 'westus'):
    self.__key = key
    self.__region = region
    self.__session = aiohttp.ClientSession()

  async def speech_to_text(self, audio: bytes) -> str:
    headers = {
      'Ocp-Apim-Subscription-Key': self.__key,
      'Content-Type': 'audio/ogg',
    }
    response = await self.__session.post(f"https://{self.__region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1?language=en-US", headers=headers, data=audio)
    return (await response.json())['DisplayText']

  async def text_to_speech(self, text: str) -> bytes:
    name = 'en-US-JennyMultilingualNeural'

    headers = {
      'Ocp-Apim-Subscription-Key': self.__key,
      'Content-Type': 'application/ssml+xml',
      'X-Microsoft-OutputFormat': 'ogg-48khz-16bit-mono-opus',
    }
    data = f"""
    <speak version='1.0' xml:lang='en-US'>
      <voice xml:gender='Female' name='{name}'>
        {text}
      </voice>
    </speak>
    """

    response = await self.__session.post(f"https://{self.__region}.tts.speech.microsoft.com/cognitiveservices/v1", headers=headers, data=data)
    return await response.content.read()
