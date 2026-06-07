"""
Intent Classifier
=================
LLM-based intent classification for test-related intents.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import json

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType

logger = get_logger(__name__)


class ClassifiedIntent(BaseModel):
    """Structured output from intent classification."""
    intent: IntentType = Field(..., description="Classified intent type")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score")
    entities: Dict[str, Any] = Field(default_factory=dict, description="Extracted entities")
    requires_clarification: bool = Field(default=False, description="Whether clarification needed")
    clarification_question: Optional[str] = Field(default=None, description="Question to ask if clarification needed")
    reasoning: Optional[str] = Field(default=None, description="Brief explanation of classification")


INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for a test automation assistant called WEGA Test Orchestrator.
Your job is to understand what the user wants to do and classify it into one of the supported test-related intents.

## Supported Intents:
1. **generate_test_cases** - User wants to generate test scenarios from user stories
   - Keywords: "test scenarios", "create scenarios", "testing scenarios", "generate scenarios"
   
2. **generate_test_script** - User wants to generate automated test scripts from test cases
   - Keywords: "test scripts", "automation scripts", "selenium", "playwright", "generate scripts"
   
3. **generate_test_data** - User wants to generate test data from test cases
   - Keywords: "test data", "generate data", "data generation", "test data generator"
   
4. **general_question** - General questions about the system or testing process
   - Keywords: "how do I", "what is", "help", "explain"
   
5. **unknown** - Cannot determine intent clearly

## Context Information:
{context}

## Conversation History:
{history}

## Current User Message:
{message}

## Instructions:
1. Analyze the user's message considering the conversation history
2. Classify into ONE of the intents above
3. Extract any entities (user story references, framework types, etc.)
4. If the intent is ambiguous, set requires_clarification=true

Respond with a JSON object:
{{
    "intent": "one of the intent types",
    "confidence": 0.0-1.0,
    "entities": {{"key": "value"}},
    "requires_clarification": false,
    "clarification_question": null,
    "reasoning": "brief explanation"
}}
"""


class IntentClassifier:
    """LLM-based intent classifier for test orchestrator."""
    
    def __init__(self, llm_client=None):
        logger.info("[intent_classifier.py] IntentClassifier.__init__: ENTRY")
        self._llm = llm_client
        self._llm_type = "uninitialized"
        self._initialized = False
        logger.info("[intent_classifier.py] IntentClassifier.__init__: EXIT")
    
    def _initialize_llm(self):
        """Initialize the LLM client (lazy initialization)."""
        logger.info("[intent_classifier.py] IntentClassifier._initialize_llm: ENTRY")
        if self._initialized:
            logger.info("[intent_classifier.py] IntentClassifier._initialize_llm: EXIT - already initialized")
            return
        self._initialized = True
        
        if self._llm is not None:
            return
            
        if settings.google_api_key:
            try:
                from google import genai
                import httpx
                import certifi
                
                ssl_verify = certifi.where() if settings.ssl_verify else False
                if not settings.ssl_verify:
                    logger.warning("SSL verification disabled for Google GenAI")
                http_client = httpx.Client(verify=ssl_verify)
                
                self._llm = genai.Client(
                    api_key=settings.google_api_key,
                    http_options={"client": http_client}
                )
                self._llm_type = "google"
                logger.info("Initialized Google GenAI for intent classification")
                return
            except Exception as e:
                logger.warning("Failed to initialize Google GenAI", error=str(e))
        
        if settings.google_cloud_project:
            try:
                from langchain_google_vertexai import ChatVertexAI
                self._llm = ChatVertexAI(
                    model="gemini-1.5-flash",
                    temperature=settings.llm_temperature,
                    project=settings.google_cloud_project,
                    location=settings.google_cloud_location
                )
                self._llm_type = "vertexai"
                logger.info("Initialized Vertex AI (Gemini) for intent classification")
                return
            except Exception as e:
                logger.warning("Failed to initialize Vertex AI", error=str(e))
        
        if settings.openai_api_key:
            try:
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=settings.llm_temperature,
                    api_key=settings.openai_api_key,
                    max_tokens=settings.llm_max_tokens
                )
                self._llm_type = "openai"
                logger.info("Initialized OpenAI for intent classification (fallback)")
                return
            except Exception as e:
                logger.warning("Failed to initialize OpenAI", error=str(e))
        
        self._llm_type = "fallback"
        logger.warning("No LLM available, using keyword-based fallback")
        logger.info("[intent_classifier.py] IntentClassifier._initialize_llm: EXIT", llm_type=self._llm_type)
    
    async def classify(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedIntent:
        """Classify user intent from message."""
        logger.info("[intent_classifier.py] IntentClassifier.classify: ENTRY", message=message[:50] if message else "")
        logger.debug(
            "Classify method called",
            message=message,
            history_count=len(history) if history else 0,
            context=context
        )
        
        # Lazy initialization on first use
        if not self._initialized:
            logger.debug("LLM not initialized, initializing now")
            self._initialize_llm()
        
        history = history or []
        context = context or {}
        
        history_str = "\n".join([
            f"{m['role'].capitalize()}: {m['content']}"
            for m in history[-5:]
        ]) if history else "No previous conversation"
        
        context_str = json.dumps(context, indent=2) if context else "No additional context"
        
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            context=context_str,
            history=history_str,
            message=message
        )
        
        logger.debug("Classification prompt prepared", llm_type=self._llm_type, prompt_length=len(prompt))
        
        try:
            if self._llm_type == "google":
                logger.debug("Using Google GenAI for classification")
                result = await self._classify_with_google(prompt)
            elif self._llm_type == "vertexai":
                logger.debug("Using Vertex AI for classification")
                result = await self._classify_with_vertexai(prompt)
            elif self._llm_type == "openai":
                logger.debug("Using OpenAI for classification")
                result = await self._classify_with_openai(prompt)
            else:
                logger.debug("Using keyword fallback for classification")
                result = self._classify_with_keywords(message)
            
            logger.info(
                "Classified intent",
                intent=result.intent.value,
                confidence=result.confidence,
                message_preview=message[:50],
                llm_type=self._llm_type
            )
            logger.debug("Classification result details", result=result.model_dump())
            logger.info("[intent_classifier.py] IntentClassifier.classify: EXIT", intent=result.intent.value)
            return result
            
        except Exception as e:
            logger.error(
                "LLM intent classification failed, falling back to keywords",
                error=str(e),
                error_type=type(e).__name__,
                llm_type=self._llm_type,
                exc_info=True
            )
            result = self._classify_with_keywords(message)
            result.reasoning = f"Keyword fallback (LLM error: {str(e)[:50]})"
            logger.debug("Keyword fallback result", result=result.model_dump())
            logger.info("[intent_classifier.py] IntentClassifier.classify: EXIT - fallback", intent=result.intent.value)
            return result
    
    async def _classify_with_google(self, prompt: str) -> ClassifiedIntent:
        """Classify using Google GenAI."""
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_google: ENTRY")
        from google.genai import types
        
        logger.debug("Google GenAI request", prompt_length=len(prompt))
        response = self._llm.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        logger.debug("Google GenAI response received", response_text=response.text[:500] if response.text else None)
        result_json = json.loads(response.text)
        logger.debug("Google GenAI parsed response", result_json=result_json)
        result = self._parse_classification_result(result_json)
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_google: EXIT", intent=result.intent.value)
        return result
    
    async def _classify_with_vertexai(self, prompt: str) -> ClassifiedIntent:
        """Classify using Vertex AI (Gemini)."""
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_vertexai: ENTRY")
        from langchain_core.messages import HumanMessage
        
        logger.debug("Vertex AI request", prompt_length=len(prompt))
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        logger.debug("Vertex AI response received", response_content=content[:500] if content else None)
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            result_json = json.loads(content[start:end])
            logger.debug("Vertex AI parsed response", result_json=result_json)
            result = self._parse_classification_result(result_json)
            logger.info("[intent_classifier.py] IntentClassifier._classify_with_vertexai: EXIT", intent=result.intent.value)
            return result
        logger.error("No JSON found in Vertex AI response", content=content)
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_vertexai: EXIT - error")
        raise ValueError("No JSON found in response")
    
    async def _classify_with_openai(self, prompt: str) -> ClassifiedIntent:
        """Classify using OpenAI (fallback)."""
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_openai: ENTRY")
        from langchain_core.messages import HumanMessage
        
        logger.debug("OpenAI request", prompt_length=len(prompt))
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        logger.debug("OpenAI response received", response_content=content[:500] if content else None)
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            result_json = json.loads(content[start:end])
            logger.debug("OpenAI parsed response", result_json=result_json)
            result = self._parse_classification_result(result_json)
            logger.info("[intent_classifier.py] IntentClassifier._classify_with_openai: EXIT", intent=result.intent.value)
            return result
        logger.error("No JSON found in OpenAI response", content=content)
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_openai: EXIT - error")
        raise ValueError("No JSON found in response")
    
    def _classify_with_keywords(self, message: str) -> ClassifiedIntent:
        """Fallback keyword-based classification for test intents."""
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_keywords: ENTRY", message=message[:50] if message else "")
        message_lower = message.lower().strip()
        logger.debug("Keyword classification started", message=message_lower)
        
        # Check for confirmation words first
        confirmation_words = [
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed", 
            "continue", "go ahead", "do it", "confirm", "confirmed", "correct",
            "right", "absolutely", "definitely", "please", "yes please", "let's go",
            "sounds good", "that's right", "go for it", "make it so"
        ]
        
        if message_lower in confirmation_words or any(
            message_lower == word or message_lower.startswith(word + " ") or message_lower.endswith(" " + word)
            for word in confirmation_words
        ):
            logger.debug("Keyword match: confirmation", message=message_lower)
            logger.info("[intent_classifier.py] IntentClassifier._classify_with_keywords: EXIT", intent="confirmation")
            return ClassifiedIntent(
                intent=IntentType.CONFIRMATION,
                confidence=0.9,
                reasoning="User confirmed/agreed to proceed"
            )
        
        # Test-specific keyword mapping
        keyword_intents = [
            (["test scenario", "test scenarios", "generate scenario", "create scenario", "testing scenario", "test case", "test cases", "testcase", "testcases"], IntentType.GENERATE_TEST_CASES),
            (["test script", "automation", "selenium", "playwright", "generate script", "automation script"], IntentType.GENERATE_TEST_SCRIPT),
            (["test data", "testdata", "generate data", "data generation", "test data generator"], IntentType.GENERATE_TEST_DATA),
            (["how do", "what is", "help", "explain"], IntentType.GENERAL_QUESTION),
        ]
        
        for keywords, intent in keyword_intents:
            if any(kw in message_lower for kw in keywords):
                logger.debug("Keyword match found", intent=intent.value, matched_keywords=[kw for kw in keywords if kw in message_lower])
                logger.info("[intent_classifier.py] IntentClassifier._classify_with_keywords: EXIT", intent=intent.value)
                return ClassifiedIntent(
                    intent=intent,
                    confidence=0.7,
                    reasoning="Matched by keyword"
                )
        
        logger.debug("No keyword match, returning unknown intent", message=message_lower)
        logger.info("[intent_classifier.py] IntentClassifier._classify_with_keywords: EXIT", intent="unknown")
        return ClassifiedIntent(
            intent=IntentType.UNKNOWN,
            confidence=0.3,
            requires_clarification=True,
            clarification_question="I'm not sure what you'd like to do. Could you please clarify? "
                                   "For example: Generate test scenarios or Create test scripts?"
        )
    
    def _parse_classification_result(self, result: Dict[str, Any]) -> ClassifiedIntent:
        """Parse LLM response into ClassifiedIntent."""
        logger.info("[intent_classifier.py] IntentClassifier._parse_classification_result: ENTRY")
        intent_str = result.get("intent", "unknown").lower()
        
        intent_mapping = {
            "generate_test_cases": IntentType.GENERATE_TEST_CASES,
            "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
            "general_question": IntentType.GENERAL_QUESTION,
            "confirmation": IntentType.CONFIRMATION,
        }
        
        intent = intent_mapping.get(intent_str, IntentType.UNKNOWN)
        
        classified = ClassifiedIntent(
            intent=intent,
            confidence=result.get("confidence", 0.5),
            entities=result.get("entities", {}),
            requires_clarification=result.get("requires_clarification", False),
            clarification_question=result.get("clarification_question"),
            reasoning=result.get("reasoning")
        )
        logger.info("[intent_classifier.py] IntentClassifier._parse_classification_result: EXIT", intent=intent.value)
        return classified


_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """Get the global classifier instance."""
    logger.info("[intent_classifier.py] get_classifier: ENTRY")
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = IntentClassifier()
    logger.info("[intent_classifier.py] get_classifier: EXIT")
    return _classifier_instance
