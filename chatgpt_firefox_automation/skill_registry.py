"""
Skill Registry - NVIDIA labs-OO-Agents Style

Central registry for skill discovery, validation, and execution.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .text_skill import TextSkill, SkillInput, SkillOutput, SkillResult

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Central registry for skill discovery and management.
    
    Features:
    - Skill registration and discovery
    - Schema validation
    - Dependency resolution
    - Skill composition
    """
    
    def __init__(self):
        self._skills: Dict[str, Type[TextSkill]] = {}
        self._instances: Dict[str, TextSkill] = {}
        self._schemas: Dict[str, Dict] = {}
    
    def register(self, skill_class: Type[TextSkill]) -> Type[TextSkill]:
        """Register a skill class"""
        if not issubclass(skill_class, TextSkill):
            raise ValueError(f"{skill_class} must inherit from TextSkill")
        
        skill_name = skill_class.name
        if skill_name in self._skills:
            logger.warning(f"Overwriting existing skill: {skill_name}")
        
        self._skills[skill_name] = skill_class
        self._schemas[skill_name] = {
            "input": skill_class.input_model.model_json_schema(),
            "output": skill_class.output_model.model_json_schema(),
            "description": skill_class.description,
        }
        logger.info(f"Registered skill: {skill_name}")
        return skill_class
    
    def get(self, name: str) -> Optional[Type[TextSkill]]:
        """Get skill class by name"""
        return self._skills.get(name)
    
    def get_instance(self, name: str, config: Optional[Dict] = None) -> Optional[TextSkill]:
        """Get or create skill instance"""
        if name not in self._skills:
            return None
        
        if name not in self._instances:
            self._instances[name] = self._skills[name](config)
        
        return self._instances[name]
    
    def list_skills(self) -> List[Dict[str, Any]]:
        """List all registered skills with schemas"""
        return [
            {
                "name": name,
                "description": self._schemas[name]["description"],
                "input_schema": self._schemas[name]["input"],
                "output_schema": self._schemas[name]["output"],
            }
            for name in self._skills
        ]
    
    def validate_input(self, skill_name: str, input_data: Dict) -> bool:
        """Validate input against skill schema"""
        skill = self._skills.get(skill_name)
        if not skill:
            return False
        try:
            skill.input_model.model_validate(input_data)
            return True
        except Exception:
            return False
    
    def load_from_directory(self, path: Path) -> int:
        """Auto-discover and load skills from directory"""
        count = 0
        for py_file in path.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                module_name = py_file.stem
                spec = __import__(f"{path.name}.{module_name}", fromlist=["*"])
                for attr_name in dir(spec):
                    attr = getattr(spec, attr_name)
                    if isinstance(attr, type) and issubclass(attr, TextSkill) and attr != TextSkill:
                        self.register(attr)
                        count += 1
            except Exception as e:
                logger.debug(f"Failed to load skill from {py_file}: {e}")
        return count
    
    def to_manifest(self) -> Dict[str, Any]:
        """Export as browser-act skill manifest"""
        return {
            "name": "chatgpt-firefox-automation",
            "version": "1.0.0",
            "skills": self.list_skills(),
        }
    
    def save_manifest(self, path: Path):
        """Save manifest to file"""
        path.write_text(json.dumps(self.to_manifest(), indent=2))


# Global registry instance
_registry = SkillRegistry()


def register_skill(skill_class: Type[TextSkill]) -> Type[TextSkill]:
    """Decorator to register a skill"""
    return _registry.register(skill_class)


def get_registry() -> SkillRegistry:
    """Get global registry instance"""
    return _registry
