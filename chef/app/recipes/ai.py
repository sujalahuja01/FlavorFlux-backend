import requests
import json
from dotenv import load_dotenv
import os
import pathlib
import re

from google import genai
from google.genai import types

env_path = pathlib.Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

YT_KEY = os.getenv("YT_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")

client = genai.Client(api_key=GEMINI_KEY)


def call_ai(ingredients, cuisine=None, previous_title=None):
    formatted_ingredients = ", ".join(ingredients) if isinstance(ingredients, list) else str(ingredients)
    
    
    system_prompt = (
    "You are an assistant that receives a list of ingredients and optionally a cuisine, "
    "and suggests a recipe the user can make with some or all of those ingredients. "
    "The recipe title should be 2-3 words long maximum. Include the total time required to cook the recipe. "
    "If the ingredients or cuisine are invalid or gibberish, skip the cuisine and generate a recipe based on the ingredients. "
    "You don't need to use every ingredient, but try not to include too many extras. "
    "Steps should be concise, 1-2 sentences per step, giving helpful guidance but not too verbose. "
    "ALWAYS respond strictly in the following raw JSON format, with no extra text, markdown, or code blocks. "
    "Ingredients should include the quantities used in the recipe and be a comma-separated string. "
    "Steps should be a \\n-separated string of concise instructions (do not include numbers or bullets).\n"
    "Example:\n"
    '{'
    '"title": "Berry Cream Crostini",'
    '"cuisine": "Italian",'
    '"ingredients": "4 slices bread, 100g cream cheese, 1 cup mixed berries, 2 tbsp sugar, pinch lemon zest",'
    '"steps": "Slice strawberries and pit cherries carefully. Set aside a few berries for garnish.\\nIn a bowl, mix cream cheese and sugar until smooth. Optionally, add lemon zest.\\nCook half the berries with 1 tbsp sugar until syrupy. Let cool.\\nToast bread until golden.\\nSpread cheese, top with compote and fresh berries.",'
    '"time": "15 minutes"'
    '}'
)


    edited_text =  f" Do not suggest the recipe titled '{previous_title}'. Please recommend a different recipe." if previous_title else ""
    user_prompt = f"I have {formatted_ingredients}. "

    if cuisine:
        user_prompt += f"Please give me a recipe from {cuisine} cuisine you'd recommend I make! {edited_text}"
    else:
        user_prompt += f"Please give me a recipe you'd recommend I make! {edited_text} "

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            ),
            contents=user_prompt
        )

        raw_text = response.text
        raw_text = re.sub(r"[\x00-\x09\x0b-\x1f\x7f]","", raw_text)

        pattern = r"\{.*\}"
        match = re.search(pattern, raw_text, re.DOTALL)
        if not match:
            return {"success": False, "error": "AI did not return JSON"}

        json_str = match.group()

        try:
            ai_recipe = json.loads(json_str)
        except json.JSONDecodeError:
            json_str_clean = json_str.replace("\n", "\\n")
            ai_recipe = json.loads(json_str_clean)

        urls = get_video(ai_recipe.get("title"))
        if urls:
            yt_link = urls["video_link"]
            img_url = urls['thumbnail']
        else:
            yt_link = None
            img_url = None

        return {
            "success": True,
            "title": ai_recipe.get("title"),
            "cuisine": ai_recipe.get("cuisine"),
            "ingredients": ai_recipe.get("ingredients"),
            "steps": ai_recipe.get("steps"),
            "youtube_link": yt_link,
            "img_url": img_url,
            "time": ai_recipe.get("time")
        }
    except Exception as e:
        return {"success":False, "error": str(e)}

def get_video(video):
    for duration in ["medium", "short"]:
        params = {
            'part': 'snippet',
            'q': f'how to make {video}  ',
            'type': 'video',
            'maxResults': 1,
            'order': 'relevance',
            'videoDuration': duration,
            'key': YT_KEY
        }
        try:
            response = requests.get('https://www.googleapis.com/youtube/v3/search', params=params)
            response.raise_for_status()
            data = response.json()
            item = data.get("items", [])
            if item:
                video_id = item[0]["id"]["videoId"]
                snippet = item[0]["snippet"]
                thumbnail_url = snippet["thumbnails"].get("high", {}).get("url") \
                                or snippet["thumbnails"].get("medium", {}).get("url") \
                                or snippet["thumbnails"].get("default", {}).get("url")
                return {
                    "video_link": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail": thumbnail_url
                }
        except requests.exceptions.RequestException as e:
            print(f"Error fetching YouTube video for duration {duration}: {e}")
            continue
    return None
