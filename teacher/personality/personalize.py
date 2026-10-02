import os
import sys
import json
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))#For import util Package
from util.model import call_LLM_sync

script_dir = os.path.dirname(os.path.abspath(__file__))

def personalize(personality_theory: str):
    if personality_theory == "":
        raise ValueError("Please provide a theory of personality")
    #Generate personality by theory
    #P_N:Positive_Negative
    #V_S:Vivid_Stiff
    #It can also increase the weight of reflection, the number of counter-responding frequencies of observation weight control, the length of the thought chain weight control chain, the quality of the summary of teaching materials, etc
    prompt = """
    You are a psychology and personality researcher. From the supplied theory, identify a concise set of distinct personality traits that could shape a simulated teacher's behavior.

    Return strict JSON only. Each trait name must be in English. Each trait object must contain exactly:
    - "index": a number from 0 to 10 describing the trait level
    - "P_N_weight": a number from -1 to 1 describing the trait's effect on positivity versus negativity. Positive values increase positivity; negative values increase negativity. Larger absolute values mean a stronger effect.
    - "V_S_weight": a number from -1 to 1 describing the trait's effect on vivid versus restrained speech. Positive values make speech more vivid; negative values make it more restrained. Larger absolute values mean a stronger effect.

    Use values from 0 to 0.3 for a small effect, 0.3 to 0.7 for a moderate effect, and 0.7 to 1 for a strong effect. Do not add explanations or fields.

    Example:
    {
      "Extraversion": {"index": 4, "P_N_weight": 0.8, "V_S_weight": 0.7},
      "Openness to Experience": {"index": 6, "P_N_weight": 0.5, "V_S_weight": 0.6},
      "Agreeableness": {"index": 5, "P_N_weight": 0.7, "V_S_weight": 0.4}
    }
    """
    response = call_LLM_sync(
        "teacher",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Personality theory:\n{personality_theory}\nReturn the JSON requested above, in English."}
        ],
        response_format={
            'type': 'json_object'
        }
    )
    traits_file = os.path.join(script_dir, "traits.json")
    #Deposit json Documentation
    with open(traits_file, "w", encoding='utf-8') as f:
        f.write(response)

if __name__ == "__main__":
    personalize()