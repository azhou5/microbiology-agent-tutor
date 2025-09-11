# ===============================================
# prepare_reward_data.py
# ===============================================
"""
Parse `feedback.log` ➟ dump:
   preference_pairs.jsonl   # {"prompt": ..., "chosen": ..., "rejected": ...}
   scored_samples.jsonl     # {"text": ..., "score": float}
"""

import json
from pathlib import Path
from collections import defaultdict

SRC = Path("feedback.log")
PAIR_OUT = Path("preference_pairs.jsonl")
SCORE_OUT = Path("scored_samples.jsonl")

def hist_to_prompt(hist):
    """Concatenate visible_chat_history into a single prompt string."""
    lines = []
    for msg in hist:
        role = msg["role"]
        content = msg["content"].strip()
        lines.append(f"{role.title()}: {content}")
    return "\n".join(lines) + "\nAssistant:"

def main():
    # ​——— pass 1 — aggregate answers by prompt  
    by_prompt = defaultdict(list)   # prompt → list[(answer, rating, replacement)]
    with SRC.open() as fp:
        for line in fp:
            rec = json.loads(line.split(" - INFO - ")[-1])
            prompt = hist_to_prompt(rec["visible_chat_history"])
            answer = rec["rated_message"]
            rating = int(rec["rating"])
            repl   = rec.get("replacement_text", "").strip()
            by_prompt[prompt].append((answer, rating, repl))

    # ​——— write files  
    with PAIR_OUT.open("w") as p_out, SCORE_OUT.open("w") as s_out:
        for prompt, tuples in by_prompt.items():
            # 1️⃣ scored_samples (prompt+answer, rating)
            for ans, rating, _ in tuples:
                text = prompt + " " + ans
                s_out.write(json.dumps({"text": text, "score": rating}) + "\n")

            # 2️⃣ preference pairs
            for ans, rating, repl in tuples:
                if repl:                   # explicit replacement ➟ chosen vs rejected
                    p_out.write(json.dumps({
                        "prompt": prompt,
                        "chosen": repl,
                        "rejected": ans
                    }) + "\n")
            # rating-based synthetic pairs (optional & simple)
            good = [a for a,r,_ in tuples if r >= 4]
            bad  = [a for a,r,_ in tuples if r <= 2]
            for g in good:
                for b in bad:
                    p_out.write(json.dumps({
                        "prompt": prompt,
                        "chosen": g,
                        "rejected": b
                    }) + "\n")

if __name__ == "__main__":
    main()