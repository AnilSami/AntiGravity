"""
schemas.py — Pydantic schemas representing Creator Brain and Memory entities.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class CreatorProfileModel(BaseModel):
    niche: str = Field(..., description="Content niche/domain (e.g. tech, education, gaming)")
    tone: str = Field(..., description="Creator tone (e.g. high-energy, calm, analytical)")
    demographics: Dict[str, float] = Field(default_factory=dict, description="Age/gender distribution stats")
    geographic_focus: List[str] = Field(default_factory=list, description="Target countries/regions")


class CreatorGoalsModel(BaseModel):
    primary_metric: str = Field("views", description="Core growth focus metric (views, retention, subscribers)")
    subscriber_target: int = Field(10000, description="Growth goal target")
    niche_focus: List[str] = Field(default_factory=list, description="Key keywords/topics to target")


class StylePreferencesModel(BaseModel):
    font_family: str = Field("Arial Black", description="Subtitle font")
    font_size: int = Field(24, description="Font size")
    font_color: str = Field("#FFFF00", description="Text color")
    stroke_color: str = Field("#000000", description="Outline/stroke color")
    text_position_y: int = Field(15, description="Bottom padding height in percent of frame")


class EditingPreferencesModel(BaseModel):
    crop_mode: str = Field("face-tracking", description="Manual vs face-tracking vs center crop")
    camera_velocity_px: int = Field(24, description="Max speed of camera pan")
    dead_zone_px: int = Field(48, description="Camera dead zone distance")


class MusicPreferencesModel(BaseModel):
    volume_pct: int = Field(7, description="Music volume level (0-100)")
    sfx_enabled: bool = Field(True, description="Enable sound effect triggers")
    preferred_genres: List[str] = Field(default_factory=list, description="Preferred genres (e.g. ambient, cinematic)")


class PublishingScheduleModel(BaseModel):
    optimal_hours: List[int] = Field(default_factory=lambda: [12, 17, 20], description="Best posting hours")
    optimal_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], description="Best posting days (0=Monday)")


class CreatorBrainModel(BaseModel):
    brain_id: str = "default"
    creator_profile: CreatorProfileModel
    audience_profile: Dict[str, float] = Field(default_factory=dict)
    goals: CreatorGoalsModel
    updated_at: float


class CreatorPreferencesModel(BaseModel):
    pref_id: str = "default"
    style_prefs: StylePreferencesModel
    editing_prefs: EditingPreferencesModel
    music_prefs: MusicPreferencesModel
    publishing_schedule: PublishingScheduleModel
    updated_at: float
