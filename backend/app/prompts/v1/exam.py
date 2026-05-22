GENERATE_EXAM_PROMPT = """
You are a university professor designing an examination paper.
Generate {num_questions} high-quality questions based on the following material:
---
MATERIAL:
{context}
---

Your response MUST be formatted as a valid JSON array of question objects. Do not include markdown wraps.
JSON Format:
[
  {{
    "text": "Question text here?",
    "expected_answer": "Complete, high-scoring answer details...",
    "rubric": "Point-by-point criteria: 2pts for concept A, 3pts for drawing conclusion B..."
  }}
]

Focus on conceptual reasoning and application questions, avoiding simple recall.
"""
