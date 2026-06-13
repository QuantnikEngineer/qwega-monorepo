"""
Intent Classifier with Orchestrator Routing
============================================
LLM-based intent classification that determines which orchestrator should handle the request.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import json

from app.core.logging import get_logger
from app.core.config import settings, OrchestratorCapabilities
from app.models.requests import IntentType, OrchestratorType, INTENT_TO_ORCHESTRATOR

logger = get_logger(__name__)
FILE_NAME = "intent_classifier.py"


class ClassifiedIntent(BaseModel):
    """Structured output from intent classification with routing info."""
    intent: IntentType = Field(..., description="Classified intent type")
    target_orchestrator: OrchestratorType = Field(..., description="Target orchestrator")
    confidence: float = Field(..., ge=0, le=1)
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_clarification: bool = Field(default=False)
    clarification_question: Optional[str] = Field(default=None)
    reasoning: Optional[str] = Field(default=None)


INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for QUANTNIK SDLC Orchestrator.
You need to understand what the user wants and route to the appropriate orchestrator.

## Available Orchestrators:

### 1. Planning Orchestrator (HIGHEST PRIORITY for BRD/requirements)
Handles BRD and requirements-related tasks:
- **create_brd** - Create Business Requirements Document from transcript/description
- **create_user_story** - Generate user stories from BRD
- **validate_user_story** - Validate user stories against BRD
- **create_user_manual** - Create user documentation
- **brd_summary** - Get summary of a BRD. Keywords: "brd summary", "summarize brd", "summary of brd"

### 2. Test Orchestrator (HIGHEST PRIORITY for testing)
Handles testing-related tasks:
- **generate_test_cases** - Generate test cases OR test cases from user stories. Keywords: "test case", "test cases", "test scenario", "generate test"
- **generate_test_script** - Generate automated test scripts. Keywords: "test script", "test scripts", "automation script", "selenium", "playwright"
- **generate_test_data** - Generate structured test data from test cases

NOTE: "generate_test_case" should be classified as "generate_test_cases" - they are the same operation.

### 3. Common Integration Orchestrator

Handles context enrichment and knowledge base operations:
- **context_enrich_upload** - Upload documents/files to the knowledge base
- **context_enrich_ingest** - Ingest content from websites, SharePoint, repositories, or agent outputs
- **context_enrich_feedback** - Submit feedback, ratings, reviews, suggestions, comments, or corrections. Keywords: "feedback", "rating", "rate", "review", "suggestion", "suggest", "comment", "correction", "improve", "recommendation", "opinion", "thoughts"
- **context_enrich_query** - Query/search the knowledge base for specific information, ask questions about content, or general information-seeking questions. This is a FALLBACK intent when no other specific intent matches.
- **context_enrich_list_documents** - View, list, display, show, get, fetch, or retrieve documents/files that exist in the knowledge base. Use this when user wants to SEE what documents are available, not when asking questions about their content.

### CRITICAL: context_enrich_feedback Examples
**ANY message about providing feedback, rating, review, suggestion, or correction = context_enrich_feedback**

Examples (ALL of these should be classified as context_enrich_feedback):
- "give feedback" → context_enrich_feedback
- "provide feedback" → context_enrich_feedback
- "submit feedback" → context_enrich_feedback
- "rate this" → context_enrich_feedback
- "give rating" → context_enrich_feedback
- "my rating is" → context_enrich_feedback
- "review the output" → context_enrich_feedback
- "give a review" → context_enrich_feedback
- "i have a suggestion" → context_enrich_feedback
- "my suggestion is" → context_enrich_feedback
- "suggest improvement" → context_enrich_feedback
- "add comment" → context_enrich_feedback
- "leave a comment" → context_enrich_feedback
- "correction needed" → context_enrich_feedback
- "make a correction" → context_enrich_feedback
- "i want to correct" → context_enrich_feedback
- "recommend changes" → context_enrich_feedback
- "my recommendation" → context_enrich_feedback
- "share my thoughts" → context_enrich_feedback
- "my opinion is" → context_enrich_feedback
- "domain preference" → context_enrich_feedback
- "set preference" → context_enrich_feedback

### CRITICAL: context_enrich_list_documents Examples
**ANY message asking to see, view, show, list, get, fetch, or retrieve documents/files = context_enrich_list_documents**

Examples (ALL of these should be classified as context_enrich_list_documents):
- "show my files" → context_enrich_list_documents
- "fetch the documents" → context_enrich_list_documents
- "get the documents" → context_enrich_list_documents
- "list my documents" → context_enrich_list_documents
- "what files do I have" → context_enrich_list_documents
- "fetch documents" → context_enrich_list_documents
- "display uploaded files" → context_enrich_list_documents
- "what's in my knowledge base" → context_enrich_list_documents
- "show uploaded documents" → context_enrich_list_documents
- "view my files" → context_enrich_list_documents
- "what documents are available" → context_enrich_list_documents
- "retrieve my files" → context_enrich_list_documents
- "show all documents" → context_enrich_list_documents
- "my documents" → context_enrich_list_documents
- "the documents" → context_enrich_list_documents

### CRITICAL: context_enrich_query Examples (FALLBACK for information-seeking questions)
**Use context_enrich_query when user asks questions or seeks information that doesn't match Planning/Test intents:**

Question patterns (case-insensitive):
- "how to...", "how do I...", "how can I..."
- "what is...", "what are...", "what does..."
- "why is...", "why does...", "why should..."
- "when should...", "when to..."
- "where is...", "where can..."
- "which one...", "which is..."
- "can you explain...", "explain..."
- "tell me about...", "describe..."

Information retrieval patterns (case-insensitive):
- "get me...", "fetch...", "retrieve..." (when NOT about listing documents)
- "find...", "search for...", "look for..."
- "give me...", "provide...", "show me..." (when asking for information, not document listing)

Examples (ALL of these should be classified as context_enrich_query):
- "how to create a login page" → context_enrich_query
- "what is microservices architecture" → context_enrich_query
- "why should we use REST API" → context_enrich_query
- "get me information about payment gateway" → context_enrich_query
- "fetch details about user authentication" → context_enrich_query
- "retrieve the requirements for checkout flow" → context_enrich_query
- "what does the BRD say about security" → context_enrich_query
- "explain the login flow" → context_enrich_query
- "tell me about the API endpoints" → context_enrich_query
- "find information about database schema" → context_enrich_query

### 4. General
- **general_question** - General questions about the system capabilities
- **confirmation** - User confirming a previous suggestion (yes, ok, proceed, continue)
- **unknown** - Cannot determine intent clearly

## PRIORITY ORDER FOR CLASSIFICATION (CRITICAL):
1. **FIRST**: Check if message matches Planning orchestrator keywords (brd, user story, validation, summary)
2. **SECOND**: Check if message matches Test orchestrator keywords (test case, test cases, test script, test scripts, test data)
3. **THIRD**: Check if message is about document listing (list, show, fetch documents/files)
4. **FOURTH**: Check if message is about feedback, rating, review, suggestion, or correction → classify as **context_enrich_feedback**
5. **FIFTH**: Check if message is about upload or ingest
6. **LAST (FALLBACK)**: If message contains question words (how, what, why, when, where, which) OR information retrieval words (get me, fetch, retrieve, find, search) AND doesn't match above intents, classify as **context_enrich_query**

## Context Information:
{context}

## Conversation History:
{history}

## Current User Message:
{message}

## Instructions:
1. Analyze the user's message carefully (case-insensitive matching)
2. If user is confirming (yes, ok, proceed, continue), classify as "confirmation"
3. **PRIORITY CHECK**: First check for Planning keywords (brd, summary, user story) - if matched, route to Planning
4. **PRIORITY CHECK**: Then check for Test keywords (test case, test cases, test script, test scripts) - if matched, route to Test
5. **DOCUMENT LISTING**: If user wants to VIEW, LIST, SHOW documents/files, classify as "context_enrich_list_documents"
6. **FALLBACK TO QUERY**: If message contains question words (how, what, why, when, where, which, can, explain, tell, describe) OR retrieval words (get me, fetch, retrieve, find, search, give me, provide) AND doesn't match Planning/Test intents, classify as "context_enrich_query" and route to "common_integration"
7. Route to "planning" for BRD/requirements, "test" for testing, "common_integration" for query/document operations
8. **NEVER classify information-seeking questions as "unknown"** - use context_enrich_query as fallback
9. Extract relevant entities

Respond with JSON:
{{
    "intent": "one of the intent types",
    "target_orchestrator": "planning" or "test" or "common_integration" or "unknown",
    "confidence": 0.0-1.0,
    "entities": {{}},
    "requires_clarification": false,
    "clarification_question": null,
    "reasoning": "brief explanation"
}}
"""


class IntentClassifier:
    """LLM-based intent classifier with orchestrator routing."""
    
    def __init__(self, llm_client=None):
        logger.info("[IntentClassifier.__init__] Initializing intent classifier")
        self._llm = llm_client
        self._initialize_llm()
    
    def _initialize_llm(self):
        """Initialize the LLM client."""
        logger.debug("[IntentClassifier._initialize_llm] Starting LLM initialization")
        if self._llm is not None:
            logger.debug("[IntentClassifier._initialize_llm] LLM client already provided, skipping initialization")
            return
            
        if settings.google_api_key:
            try:
                logger.debug("[IntentClassifier._initialize_llm] Attempting Google GenAI initialization")
                from google import genai
                import httpx
                import certifi
                
                ssl_verify = certifi.where() if settings.ssl_verify else False
                http_client = httpx.Client(verify=ssl_verify, timeout=900)
                
                self._llm = genai.Client(
                    api_key=settings.google_api_key,
                    http_options={"client": http_client}
                )
                self._llm_type = "google"
                logger.info("[IntentClassifier._initialize_llm] Initialized Google GenAI for intent classification")
                return
            except Exception as e:
                logger.warning(
                    "[IntentClassifier._initialize_llm] Failed to initialize Google GenAI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        if settings.google_cloud_project:
            try:
                logger.debug("[IntentClassifier._initialize_llm] Attempting Vertex AI initialization")
                from langchain_google_vertexai import ChatVertexAI
                self._llm = ChatVertexAI(
                    model="gemini-1.5-flash",
                    temperature=settings.llm_temperature,
                    project=settings.google_cloud_project,
                    location=settings.google_cloud_location
                )
                self._llm_type = "vertexai"
                logger.info("[IntentClassifier._initialize_llm] Initialized Vertex AI for intent classification")
                return
            except Exception as e:
                logger.warning(
                    "[IntentClassifier._initialize_llm] Failed to initialize Vertex AI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        if settings.openai_api_key:
            try:
                logger.debug("[IntentClassifier._initialize_llm] Attempting OpenAI initialization")
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=settings.llm_temperature,
                    api_key=settings.openai_api_key,
                    max_tokens=settings.llm_max_tokens
                )
                self._llm_type = "openai"
                logger.info("[IntentClassifier._initialize_llm] Initialized OpenAI for intent classification")
                return
            except Exception as e:
                logger.warning(
                    "[IntentClassifier._initialize_llm] Failed to initialize OpenAI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        self._llm_type = "fallback"
        logger.warning("[IntentClassifier._initialize_llm] No LLM available, using keyword-based fallback")
    
    async def classify(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedIntent:
        """Classify user intent and determine target orchestrator."""
        logger.info(
            "[IntentClassifier.classify] Starting intent classification",
            message_length=len(message),
            message_preview=message[:100],
            history_count=len(history) if history else 0,
            has_context=context is not None,
            llm_type=self._llm_type
        )
        
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
        
        logger.debug(
            "[IntentClassifier.classify] Classification prompt prepared",
            prompt_length=len(prompt),
            history_str_length=len(history_str),
            context_str_length=len(context_str)
        )
        
        try:
            if self._llm_type == "google":
                logger.debug("[IntentClassifier.classify] Using Google GenAI for classification")
                result = await self._classify_with_google(prompt)
            elif self._llm_type == "vertexai":
                logger.debug("[IntentClassifier.classify] Using Vertex AI for classification")
                result = await self._classify_with_langchain(prompt)
            elif self._llm_type == "openai":
                logger.debug("[IntentClassifier.classify] Using OpenAI for classification")
                result = await self._classify_with_langchain(prompt)
            else:
                logger.debug("[IntentClassifier.classify] Using keyword fallback for classification")
                result = self._classify_with_keywords(message, context)
            
            logger.info(
                "[IntentClassifier.classify] Intent classification completed",
                intent=result.intent.value,
                orchestrator=result.target_orchestrator.value,
                confidence=result.confidence,
                requires_clarification=result.requires_clarification,
                reasoning=result.reasoning,
                entities=result.entities
            )
            return result
            
        except Exception as e:
            logger.error(
                "[IntentClassifier.classify] LLM classification failed, falling back to keywords",
                error=str(e),
                error_type=type(e).__name__,
                llm_type=self._llm_type,
                message_preview=message[:100]
            )
            result = self._classify_with_keywords(message, context)
            result.reasoning = f"Keyword fallback (LLM error: {str(e)[:50]})"
            logger.info(
                "[IntentClassifier.classify] Keyword fallback classification completed",
                intent=result.intent.value,
                orchestrator=result.target_orchestrator.value,
                confidence=result.confidence
            )
            return result
    
    async def _classify_with_google(self, prompt: str) -> ClassifiedIntent:
        """Classify using Google GenAI."""
        logger.debug("[IntentClassifier._classify_with_google] Starting Google GenAI classification")
        from google.genai import types
        
        logger.debug(
            "[IntentClassifier._classify_with_google] Sending request to Google GenAI",
            model="gemini-2.0-flash",
            prompt_length=len(prompt)
        )
        
        response = self._llm.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        logger.debug(
            "[IntentClassifier._classify_with_google] Google GenAI response received",
            response_text=response.text[:500] if response.text else None
        )
        
        result_json = json.loads(response.text)
        logger.debug(
            "[IntentClassifier._classify_with_google] Parsed JSON response",
            result=result_json
        )
        return self._parse_result(result_json)
    
    async def _classify_with_langchain(self, prompt: str) -> ClassifiedIntent:
        """Classify using LangChain (Vertex AI or OpenAI)."""
        logger.debug(
            "[IntentClassifier._classify_with_langchain] Starting LangChain classification",
            llm_type=self._llm_type
        )
        from langchain_core.messages import HumanMessage
        
        logger.debug(
            "[IntentClassifier._classify_with_langchain] Sending request to LangChain LLM",
            prompt_length=len(prompt)
        )
        
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        
        logger.debug(
            "[IntentClassifier._classify_with_langchain] LangChain response received",
            response_content=content[:500] if content else None
        )
        
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            result_json = json.loads(content[start:end])
            logger.debug(
                "[IntentClassifier._classify_with_langchain] Parsed JSON response",
                result=result_json
            )
            return self._parse_result(result_json)
        
        logger.error(
            "[IntentClassifier._classify_with_langchain] No JSON found in LLM response",
            response_content=content[:500]
        )
        raise ValueError("No JSON found in response")
    
    def _classify_with_keywords(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedIntent:
        """Fallback keyword-based classification with orchestrator routing.
        
        Priority order:
        1. Confirmation words
        2. Planning orchestrator keywords (brd, user story, etc.)
        3. Test orchestrator keywords (test case, test script, etc.)
        4. List documents keywords
        5. Other common integration keywords (upload, ingest, feedback)
        6. FALLBACK: Question/query patterns -> context_enrich_query
        """
        logger.debug(
            f"[{FILE_NAME}] _classify_with_keywords: ENTRY",
            message=message,
            context=context
        )
        message_lower = message.lower().strip()
        context = context or {}
        
        # Check for confirmation words
        confirmation_words = [
            "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "proceed", 
            "continue", "go ahead", "do it", "confirm", "confirmed", "correct",
            "right", "absolutely", "definitely", "please", "yes please",
            "sounds good", "let's go", "make it so", "1", "2", "3",
            "first", "second", "third", "option 1", "option 2", "option 3"
        ]
        
        if message_lower in confirmation_words or any(
            message_lower == word or message_lower.startswith(word + " ")
            for word in confirmation_words
        ):
            last_orch = context.get("last_orchestrator", "unknown")
            logger.debug(
                f"[{FILE_NAME}] _classify_with_keywords: Matched confirmation word",
                message=message_lower,
                last_orchestrator=last_orch
            )
            return ClassifiedIntent(
                intent=IntentType.CONFIRMATION,
                target_orchestrator=OrchestratorType(last_orch) if last_orch in ["planning", "test"] else OrchestratorType.UNKNOWN,
                confidence=0.9,
                reasoning="User confirmed/agreed to proceed"
            )
        
        # PRIORITY 1: Planning orchestrator keywords (highest priority for BRD/requirements)
        planning_keywords = [
            (["create brd", "generate brd", "business requirements", "from transcript"], IntentType.CREATE_BRD),
            (["create user stor", "generate user stor", "user story from", "generate stories"], IntentType.CREATE_USER_STORY),
            (["validate", "verify user stor", "check stor", "validation"], IntentType.VALIDATE_USER_STORY),
            (["user manual", "documentation", "create manual"], IntentType.CREATE_USER_MANUAL),
            (["brd summary", "summarize brd", "summary of brd", "brd overview"], IntentType.BRD_SUMMARY),
        ]
        
        for keywords, intent in planning_keywords:
            if any(kw in message_lower for kw in keywords):
                matched_kw = [kw for kw in keywords if kw in message_lower]
                logger.debug(
                    f"[{FILE_NAME}] _classify_with_keywords: Matched planning keywords",
                    matched_keywords=matched_kw,
                    intent=intent.value
                )
                return ClassifiedIntent(
                    intent=intent,
                    target_orchestrator=OrchestratorType.PLANNING,
                    confidence=0.8,
                    reasoning="Matched planning keywords"
                )
        
        # PRIORITY 2: Test orchestrator keywords (highest priority for testing)
        test_keywords = [
            (["test case", "test cases", "test scenario", "test scenarios", "generate test cases", 
              "create test case", "generate test case", "testing scenario", "create scenario"], IntentType.GENERATE_TEST_CASES),
            (["test script", "test scripts", "automation script", "automation scripts", "selenium", 
              "playwright", "automated test", "generate script", "create script"], IntentType.GENERATE_TEST_SCRIPT),
            (["test data", "testdata", "generate data", "data generation", "test data generator"], IntentType.GENERATE_TEST_DATA),
        ]
        
        for keywords, intent in test_keywords:
            if any(kw in message_lower for kw in keywords):
                matched_kw = [kw for kw in keywords if kw in message_lower]
                logger.debug(
                    f"[{FILE_NAME}] _classify_with_keywords: Matched test keywords",
                    matched_keywords=matched_kw,
                    intent=intent.value
                )
                return ClassifiedIntent(
                    intent=intent,
                    target_orchestrator=OrchestratorType.TEST,
                    confidence=0.8,
                    reasoning="Matched test keywords"
                )
        
        # Check for list documents FIRST (before other common integration keywords)
        list_doc_keywords = ["get the document", "get the documents", "fetch the document", "fetch the documents", 
                            "get document", "get documents", "fetch document", "fetch documents",
                            "list document", "list documents", "show document", "show documents",
                            "retrieve document", "retrieve documents", "get the file", "get the files",
                            "fetch the file", "fetch the files", "list the file", "list the files",
                            "show the file", "show the files", "get all document", "list all document",
                            "list my document", "my documents", "the documents", "all documents",
                            "show my files", "get my files", "list my files", "fetch my files",
                            "my files", "all files", "list files", "show files", "get files"]
        if any(kw in message_lower for kw in list_doc_keywords):
            logger.debug(
                f"[{FILE_NAME}] _classify_with_keywords: Matched list documents keywords",
                message=message_lower
            )
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS,
                target_orchestrator=OrchestratorType.COMMON_INTEGRATION,
                confidence=0.8,
                reasoning="Matched list documents keywords"
            )
        
        # Common Integration orchestrator keywords
        common_integration_keywords = [
            (["upload", "upload file", "upload document", "add file", "add document"], IntentType.CONTEXT_ENRICH_UPLOAD),
            (["ingest", "crawl", "scrape", "import", "index website", "index repo", "sharepoint"], IntentType.CONTEXT_ENRICH_INGEST),
            (["feedback", "rate", "rating", "correct", "correction", "preference", "domain preference"], IntentType.CONTEXT_ENRICH_FEEDBACK),
            (["query knowledge", "search knowledge", "knowledge base", "find in knowledge", "look up"], IntentType.CONTEXT_ENRICH_QUERY),
        ]
        
        for keywords, intent in common_integration_keywords:
            if any(kw in message_lower for kw in keywords):
                matched_kw = [kw for kw in keywords if kw in message_lower]
                logger.debug(
                    f"[{FILE_NAME}] _classify_with_keywords: Matched common integration keywords",
                    matched_keywords=matched_kw,
                    intent=intent.value
                )
                return ClassifiedIntent(
                    intent=intent,
                    target_orchestrator=OrchestratorType.COMMON_INTEGRATION,
                    confidence=0.7,
                    reasoning="Matched common integration keywords"
                )
        
        # PRIORITY 5 (FALLBACK): Question patterns and information retrieval -> context_enrich_query
        # Question word patterns (case-insensitive)
        question_patterns = [
            "how to", "how do", "how can", "how is", "how does", "how should", "how would",
            "what is", "what are", "what does", "what do", "what should", "what would", "what can",
            "why is", "why does", "why do", "why should", "why would", "why are",
            "when to", "when should", "when do", "when does", "when is", "when can",
            "where is", "where are", "where can", "where do", "where does",
            "which is", "which are", "which one", "which should", "which would",
            "can you explain", "can you tell", "can you describe", "can you help",
            "could you explain", "could you tell", "could you describe",
            "explain", "describe", "tell me", "tell us",
            "who is", "who are", "who can", "who should",
        ]
        
        # Information retrieval patterns (case-insensitive)
        retrieval_patterns = [
            "get me", "get the", "get information", "get details", "get info",
            "fetch me", "fetch the", "fetch information", "fetch details",
            "retrieve", "retrieve the", "retrieve information",
            "find", "find me", "find the", "find information", "find details",
            "search for", "search the", "look for", "look up",
            "give me", "give the", "provide", "provide me", "provide the",
            "show me", "show the",  # when asking for information, not document listing
            "i need", "i want", "i would like",
            "help me with", "help me understand", "help with",
            "knowledge base", "query knowledge", "search knowledge", "find in knowledge",
        ]
        
        # Check if message starts with or contains question patterns
        is_question = any(message_lower.startswith(qp) or f" {qp}" in f" {message_lower}" for qp in question_patterns)
        
        # Check if message contains retrieval patterns
        is_retrieval = any(rp in message_lower for rp in retrieval_patterns)
        
        # Check if message ends with question mark
        has_question_mark = message.strip().endswith("?")
        
        if is_question or is_retrieval or has_question_mark:
            logger.debug(
                f"[{FILE_NAME}] _classify_with_keywords: Matched query/question pattern (fallback)",
                message=message_lower,
                is_question=is_question,
                is_retrieval=is_retrieval,
                has_question_mark=has_question_mark
            )
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_QUERY,
                target_orchestrator=OrchestratorType.COMMON_INTEGRATION,
                confidence=0.6,
                reasoning="Matched question/query pattern - routing to knowledge base query"
            )
        
        # Check for general system help questions only
        system_help_keywords = ["what can you do", "help me understand this tool", "system capabilities", "what features"]
        if any(kw in message_lower for kw in system_help_keywords):
            logger.debug(
                f"[{FILE_NAME}] _classify_with_keywords: Matched system help keywords",
                message=message_lower
            )
            return ClassifiedIntent(
                intent=IntentType.GENERAL_QUESTION,
                target_orchestrator=OrchestratorType.UNKNOWN,
                confidence=0.6,
                reasoning="General system question detected"
            )
        
        # Final fallback: If no patterns matched, still try context_enrich_query for any remaining queries
        logger.debug(
            f"[{FILE_NAME}] _classify_with_keywords: EXIT - No specific keywords matched, defaulting to context_enrich_query",
            message=message_lower
        )
        return ClassifiedIntent(
            intent=IntentType.CONTEXT_ENRICH_QUERY,
            target_orchestrator=OrchestratorType.COMMON_INTEGRATION,
            confidence=0.4,
            reasoning="No specific intent matched - routing to knowledge base query as fallback"
        )
    
    def _parse_result(self, result: Dict[str, Any]) -> ClassifiedIntent:
        """Parse LLM response into ClassifiedIntent."""
        logger.debug(
            f"[{FILE_NAME}] _parse_result: ENTRY",
            raw_result=result
        )
        intent_str = result.get("intent", "unknown").lower()
        orch_str = result.get("target_orchestrator", "unknown").lower()
        
        intent_mapping = {
            "create_brd": IntentType.CREATE_BRD,
            "create_user_story": IntentType.CREATE_USER_STORY,
            "validate_user_story": IntentType.VALIDATE_USER_STORY,
            "create_user_manual": IntentType.CREATE_USER_MANUAL,
            "brd_summary": IntentType.BRD_SUMMARY,
            "generate_test_cases": IntentType.GENERATE_TEST_CASES,
            "generate_test_case": IntentType.GENERATE_TEST_CASES,  # Alias - same as test scenario
            "generate_test_script": IntentType.GENERATE_TEST_SCRIPT,
            "context_enrich_upload": IntentType.CONTEXT_ENRICH_UPLOAD,
            "context_enrich_ingest": IntentType.CONTEXT_ENRICH_INGEST,
            "context_enrich_feedback": IntentType.CONTEXT_ENRICH_FEEDBACK,
            "context_enrich_query": IntentType.CONTEXT_ENRICH_QUERY,
            "context_enrich_list_documents": IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS,
            "general_question": IntentType.GENERAL_QUESTION,
            "confirmation": IntentType.CONFIRMATION,
        }
        
        orch_mapping = {
            "planning": OrchestratorType.PLANNING,
            "test": OrchestratorType.TEST,
            "common_integration": OrchestratorType.COMMON_INTEGRATION,
        }
        
        intent = intent_mapping.get(intent_str, IntentType.UNKNOWN)
        orchestrator = orch_mapping.get(orch_str, OrchestratorType.UNKNOWN)
        
        # Auto-determine orchestrator from intent if not specified
        if orchestrator == OrchestratorType.UNKNOWN and intent != IntentType.UNKNOWN:
            orchestrator = INTENT_TO_ORCHESTRATOR.get(intent, OrchestratorType.UNKNOWN)
            logger.debug(
                f"[{FILE_NAME}] _parse_result: Auto-determined orchestrator from intent",
                intent=intent.value,
                orchestrator=orchestrator.value
            )
        
        parsed = ClassifiedIntent(
            intent=intent,
            target_orchestrator=orchestrator,
            confidence=result.get("confidence", 0.5),
            entities=result.get("entities", {}),
            requires_clarification=result.get("requires_clarification", False),
            clarification_question=result.get("clarification_question"),
            reasoning=result.get("reasoning")
        )
        
        logger.debug(
            f"[{FILE_NAME}] _parse_result: EXIT",
            intent=parsed.intent.value,
            orchestrator=parsed.target_orchestrator.value,
            confidence=parsed.confidence
        )
        return parsed


_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """Get the global classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        logger.info(f"[{FILE_NAME}] get_classifier: Creating new IntentClassifier instance")
        _classifier_instance = IntentClassifier()
    return _classifier_instance
