import sys, os
sys.path.insert(0, os.path.abspath('.'))
sys.path.insert(0, os.path.abspath('../src'))
from agent.tools import AgentContext, search_knowledge_base, analyze_sentiment, create_ticket, get_or_create_customer, get_customer_history, escalate_to_human, send_response
from agent.formatters import format_response
from agents import RunContextWrapper
import json

ctx = AgentContext(run_id='test')
w = RunContextWrapper(context=ctx)

results = []

# Test 1: sentiment
r = analyze_sentiment(w, 'hello world')
results.append(f'T1 sentiment: {r}')

# Test 2: KB search
r2 = search_knowledge_base(w, 'How do I invite team members?')
results.append(f'T2 KB: found={len(r2)} chars, fallback={"No specific" in r2}')

# Test 3: create ticket
r3 = create_ticket(w, 'test@test.com', 'Test issue', 'medium', 'email')
results.append(f'T3 ticket: {r3[:80]}')

# Test 4: customer
r4 = get_or_create_customer(w, 'test@test.com', 'email')
results.append(f'T4 customer: {r4[:80]}')

# Test 5: escalate
ticket_id = r3.split()[1]
r5 = escalate_to_human(w, ticket_id, 'Test escalation')
results.append(f'T5 escalate: {r5[:80]}')

# Test 6: formatting
r6 = format_response(message='Hello', channel='whatsapp')
results.append(f'T6 format: chars={r6.character_count}, truncated={r6.truncated}')

# Test 7: angry sentiment
r7 = analyze_sentiment(w, 'This is ridiculous! I want a manager NOW!')
results.append(f'T7 angry: {r7}')

# Test 8: pricing sentiment (should be neutral)
r8 = analyze_sentiment(w, 'What is the Enterprise pricing?')
results.append(f'T8 pricing: {r8}')

for line in results:
    print(line)
