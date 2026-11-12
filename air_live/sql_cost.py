"""Rough SQL text-size estimates; never provider-reported token usage."""
import math
INPUT_USD_PER_MILLION = 0.035
OUTPUT_USD_PER_MILLION = 0.14
RATE_SOURCE = 'https://aws.amazon.com/blogs/machine-learning/effective-cost-optimization-strategies-for-amazon-bedrock/'

def estimate(system, user, output):
    # English/JSON demo heuristic, not Nova's tokenizer. Omits provider wrappers.
    incoming=math.ceil(len((system+'\n'+user).encode('utf-8'))/4)
    outgoing=math.ceil(len(output.encode('utf-8'))/4)
    return {'input_tokens':incoming,'output_tokens':outgoing,
            'cost_usd':(incoming*INPUT_USD_PER_MILLION+outgoing*OUTPUT_USD_PER_MILLION)/1_000_000,
            'method':'utf8_bytes_div_4','rate_source':RATE_SOURCE,'rate_checked':'2026-11-11'}
