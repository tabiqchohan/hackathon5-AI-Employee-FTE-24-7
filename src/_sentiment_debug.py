text = 'how do i reset my password?'
anger = ['angry', 'furious', 'ridiculous', 'unacceptable', 'terrible',
    'worst', 'horrible', 'useless', 'waste', 'scam', 'fraud',
    'damn', 'hell', 'crap', 'sucks', 'bullshit', 'wtf',
    'are you kidding', 'are you serious', 'this is insane',
    'i want to speak', 'i want to talk', 'get me a',
    'this is garbage', 'trash', 'pathetic']
frustration = ['frustrated', 'frustrating', 'annoyed', 'disappointed', 'not happy',
    'still not working', 'still broken', 'again', 'already tried',
    'this is the', 'time', 'waiting', 'waited', 'no response',
    'nobody helped', 'no one helped', 'useless support',
    'getting frustrated', 'so frustrating']
profanity = ['fuck', 'shit', 'damn', 'ass', 'bitch', 'crap', 'bastard']
positive = ['thanks', 'thank you', 'great', 'awesome', 'love', 'helpful',
    'appreciate', 'perfect', 'wonderful', 'excellent']

print(f"Checking: '{text}'")
print()

for w in anger:
    if w in text:
        print(f"ANGER MATCH: '{w}' in '{text}'")

for w in frustration:
    if w in text:
        print(f"FRUSTRATION MATCH: '{w}' in '{text}'")

for w in profanity:
    if w in text:
        print(f"PROFANITY MATCH: '{w}' in '{text}'")

for w in positive:
    if w in text:
        print(f"POSITIVE MATCH: '{w}' in '{text}'")

print("Done.")
