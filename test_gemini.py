from google import genai

client = genai.Client(
    vertexai=True,
    project="pokeagent-011",   # Tersoo Project ID
    location="us-central1"
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Hello from PokéAgent!"
)
print(response.text)
