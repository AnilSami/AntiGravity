import os
import json
import logging
import time
from typing import Optional
from analyzer import LLMResilienceManager, _extract_json_from_response

logger = logging.getLogger("upload_package")

def generate_upload_package(
    clip_text: str,
    hook: str,
    virality_score: float,
    virality_reasoning: str,
    duration: float,
    api_key: Optional[str] = None
) -> dict:
    """
    Generates a complete YouTube upload package using Claude (claude-sonnet-4-6).
    Falls back to Gemini/OpenAI if no Anthropic key is active, or uses mock data if key is 'mock'.
    """
    api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or "mock"
    
    if api_key.startswith("mock"):
        logger.info("Mock API key detected for upload package generator. Returning mock package.")
        return {
            "titles": [
                "The Shocking Truth About This Video!",
                "Why You Will Never Think The Same Way Again",
                "Nobody Is Telling You This Secret"
            ],
            "description": "The Shocking Truth About This Video! You will learn how to improve your lifestyle and mindset. This matters because it saves you time and effort. Follow for more daily insights that actually change how you think.",
            "hashtags": [
                "#shorts", "#viral", "#motivation", "#education", "#mindset",
                "#success", "#growth", "#shortsfeed", "#shortscreator", "#trending",
                "#video", "#secrets", "#truth", "#exposed", "#insights"
            ],
            "thumbnail_text": "SHOCKING TRUTH EXPOSED",
            "best_time_to_post": "Tuesdays at 6:00 PM EST",
            "target_audience": "Content creators and ambitious individuals seeking personal growth.",
            "hook_analysis": "9/10. The hook creates an instant curiosity gap that makes the user want to hear the explanation.",
            "keywords": [
                "viral shorts strategy", "how to go viral", "mindset secrets",
                "lifestyle growth", "curiosity gap hook", "content creation tips",
                "youtube shorts algorithm", "success habits", "personal growth", "exposed truth"
            ],
            "category": "Education",
            "language": "English",
            "search_intent": "Informational",
            "metadata": {
                "provider": "mock",
                "model": "mock",
                "prompt_version": "v1.1",
                "generated_at": time.time()
            }
        }

    system_prompt = "You are a YouTube Shorts growth expert who has studied what makes videos go viral."
    user_prompt = f"""Analyze this clip and generate a complete upload package optimized to maximize views, clicks, and subscribers.

Clip transcript: {clip_text}
Hook line: {hook}
Duration: {duration} seconds
Virality score: {virality_score}/10
Virality reasoning: {virality_reasoning}

Generate:

1. TITLE (3 options): Each under 60 characters. Must create curiosity or shock. Use power words (secret, truth, never, always, nobody, exposed, finally). No clickbait that doesn't deliver. Rank them 1 (best) to 3.

2. DESCRIPTION: 3-4 punchy sentences. First sentence = the hook (same energy as the title). Second sentence = what the viewer will learn/feel. Third sentence = why it matters to them personally. End with: 'Follow for more daily insights that actually change how you think.'

3. HASHTAGS: 15 hashtags. Mix of: 5 broad reach (#shorts #viral #motivation), 5 topic specific, 5 niche community tags. Research which tags perform best for this specific clip topic.

4. THUMBNAIL TEXT: One 3-5 word phrase in ALL CAPS that would stop someone scrolling. Should be the most shocking or surprising element of the clip.

5. BEST TIME TO POST: Based on the clip topic and target audience, suggest the best day and time to post for maximum reach.

6. TARGET AUDIENCE: One sentence describing exactly who this clip is for.

7. HOOK ANALYSIS: Rate the hook 1-10 and explain in one sentence why someone would or would not keep watching after the first 3 seconds.

8. KEYWORDS: 10 highly relevant search keywords/phrases.

9. CATEGORY: The optimal YouTube category for this clip (e.g., Education, Entertainment, Howto & Style).

10. LANGUAGE: The primary language of the clip (e.g., English).

11. SEARCH INTENT: The search intent targeted (e.g., Informational, Commercial, Navigational).

Return as JSON with fields: titles (array of 3), description, hashtags (array of 15), thumbnail_text, best_time_to_post, target_audience, hook_analysis, keywords (array of 10), category, language, search_intent."""

    provider = "google"
    model_used = "gemini-2.5-flash"
    
    if api_key.startswith("sk-proj-") or api_key.startswith("sk-"):
        provider = "openai"
        model_used = "gpt-4o-mini"
    elif api_key.startswith("anthropic:") or api_key.startswith("sk-ant-"):
        provider = "anthropic"
        model_used = "claude-sonnet-4-6"

    try:
        llm = LLMResilienceManager(primary_key=api_key)
        response_text = llm.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_json=True,
            model="claude-sonnet-4-6"
        )
        
        try:
            repaired_json = _extract_json_from_response(response_text)
            package = json.loads(repaired_json)
        except Exception as json_err:
            logger.warning(f"Malformed JSON returned from LLM: {json_err}. Attempting one repair/retry.")
            response_text = llm.call(
                system_prompt=system_prompt,
                user_prompt=user_prompt + "\nIMPORTANT: You must return strictly valid JSON. Do not include any markdown styling, conversational text, or trailing commas.",
                response_json=True,
                model="claude-sonnet-4-6"
            )
            repaired_json = _extract_json_from_response(response_text)
            package = json.loads(repaired_json)
        
        # Ensure missing optional fields are replaced with sensible defaults instead of causing failures
        required_fields = ["titles", "description", "hashtags", "thumbnail_text", "best_time_to_post", "target_audience", "hook_analysis", "keywords", "category", "language", "search_intent"]
        for field in required_fields:
            if field not in package or not package[field]:
                if field == "titles":
                    package["titles"] = [f"Secret Reveal: {hook[:40]}", "Why Nobody Tells You This...", "The Absolute Truth Exposed!"]
                elif field == "description":
                    package["description"] = f"The Shocking truth about this! Discover new insights. Follow for more daily insights that actually change how you think."
                elif field == "hashtags":
                    package["hashtags"] = ["#shorts", "#viral", "#motivation", "#learning", "#insight", "#success", "#growth", "#shortsfeed", "#shortscreator", "#trending", "#video", "#secrets", "#truth", "#exposed", "#daily"]
                elif field == "thumbnail_text":
                    package["thumbnail_text"] = "TRUTH EXPOSED"
                elif field == "best_time_to_post":
                    package["best_time_to_post"] = "Everyday at 5:00 PM EST"
                elif field == "target_audience":
                    package["target_audience"] = "General audience interested in learning."
                elif field == "hook_analysis":
                    package["hook_analysis"] = "7/10. Decent hook that catches initial attention."
                elif field == "keywords":
                    package["keywords"] = ["shorts", "viral", "video", "insights", "exposed", "truth", "secrets", "learning", "growth", "motivation"]
                elif field == "category":
                    package["category"] = "Education"
                elif field == "language":
                    package["language"] = "English"
                elif field == "search_intent":
                    package["search_intent"] = "Informational"
                    
        package["metadata"] = {
            "provider": provider,
            "model": model_used,
            "prompt_version": "v1.1",
            "generated_at": time.time()
        }
        return package
        
    except Exception as e:
        logger.error(f"Failed to generate upload package via LLM: {e}. Falling back to default package.")
        return {
            "titles": [
                f"Secret Reveal: {hook[:40]}",
                "Why Nobody Tells You This...",
                "The Absolute Truth Exposed!"
            ],
            "description": f"The Shocking truth about this! Discover new insights. This changes how you think daily. Follow for more daily insights that actually change how you think.",
            "hashtags": ["#shorts", "#viral", "#motivation", "#learning", "#insight", "#success", "#growth", "#shortsfeed", "#shortscreator", "#trending", "#video", "#secrets", "#truth", "#exposed", "#daily"],
            "thumbnail_text": "TRUTH EXPOSED",
            "best_time_to_post": "Everyday at 5:00 PM EST",
            "target_audience": "General audience interested in learning.",
            "hook_analysis": "7/10. Decent hook that catches initial attention.",
            "keywords": ["shorts", "viral", "video", "insights", "exposed", "truth", "secrets", "learning", "growth", "motivation"],
            "category": "Education",
            "language": "English",
            "search_intent": "Informational",
            "metadata": {
                "provider": "fallback",
                "model": "fallback",
                "prompt_version": "v1.1",
                "generated_at": time.time()
            }
        }
