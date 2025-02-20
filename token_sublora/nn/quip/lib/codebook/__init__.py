from . import latticed4, latticee8_padded12, half_integer_4bit_1col, latticee8_padded12_rvq4bit, latticee8_padded12_rvq3bit

# name: (id, codebook class)
codebook_id = {
    'D4': (0, latticed4.D4_codebook),
    'E8P12': (7, latticee8_padded12.E8P12_codebook),
    'HI4B1C': (10, half_integer_4bit_1col.HI4B1C_codebook),
    'E8P12RVQ4B': (17, latticee8_padded12_rvq4bit.E8P12RVQ4B_codebook),
    'E8P12RVQ3B': (18, latticee8_padded12_rvq3bit.E8P12RVQ3B_codebook),
}

# id from above:6quantized linear implementation
quantized_class = {
    0: latticed4.QuantizedD4Linear,
    7: latticee8_padded12.QuantizedE8P12Linear,
    10: half_integer_4bit_1col.QuantizedHI4B1CLinear,
    17: latticee8_padded12_rvq4bit.QuantizedE8P12RVQ4BLinear,
    18: latticee8_padded12_rvq3bit.QuantizedE8P12RVQ3BLinear,
}

cache_permute_set = {
    0,  # D4
}


def get_codebook(name):
    return codebook_id[name][1]()


def get_id(name):
    return codebook_id[name][0]


def get_quantized_class(id):
    return quantized_class[id]
