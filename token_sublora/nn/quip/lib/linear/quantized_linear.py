import torch
import torch.nn as nn
import quiptools_cuda
from token_sublora.nn.quip.lib.utils import dtype_from_str, get_hadK
from token_sublora.nn.quip.lib import codebook
import time


class QuantizedLinear(nn.Module):

    def __init__(self,
                 in_features,
                 out_features,
                 codesz,
                 packsz,
                 pack_out,
                 idx_dtype,
                 codebook_version,
                 outlier_channel_split=False,
                 rank=-1,
                 rescale_WH=False,
                 bias=False,
                 resid_scale_override=-1,
    ):
        super().__init__()

        self.in_features = in_features
        self.out_features = out_features
        self.outlier_channel_split = outlier_channel_split
        self.rank = rank
        self.rescale_WH = rescale_WH
        self.resid_scale_override = resid_scale_override

        self.has_bias = bias
        if self.has_bias:
            self.register_buffer('bias', torch.ones(out_features))
        
        if self.outlier_channel_split:
            self.register_buffer('ocs_dupe_inds', torch.arange(in_features))

        if self.rank > 0:
            self.register_buffer('A', torch.zeros(out_features, rank))
            self.register_buffer('B', torch.zeros(rank, in_features))
        else:
            self.A = None
            self.B = None

        if self.rescale_WH:
            self.register_buffer("scaleWH", torch.ones(in_features))
        else:
            self.scaleWH = None

        # direction we pack in, the code dimension is always in the in dimension
        if pack_out:
            self.register_buffer(
                "Qidxs",
                torch.zeros(int(out_features / packsz),
                            int(in_features / codesz),
                            dtype=dtype_from_str(idx_dtype)))
        else:
            self.register_buffer(
                "Qidxs",
                torch.zeros(out_features,
                            int(in_features / (codesz * packsz)),
                            dtype=dtype_from_str(idx_dtype)))

        self.register_buffer("codebook_id", torch.tensor(0))
        self.register_buffer("SU", torch.ones(in_features))
        self.register_buffer("SV", torch.ones(out_features))
        self.register_buffer("Wscale", torch.ones(()))

        self.built_codebook_class = False
        self.built_graph = False
        self.codebook_version = codebook_version

        had_left, K_left = get_hadK(in_features)
        had_right, K_right = get_hadK(out_features)
        self.register_buffer('had_left', had_left, persistent=False)
        self.register_buffer('had_right', had_right, persistent=False)
        self.K_left = K_left
        self.K_right = K_right
        self.packed = (packsz != 1)

    def forward(self, input):
        if not self.built_codebook_class:
            self.codebook_class = codebook.get_quantized_class(self.codebook_id.item())(
                self.Qidxs.device)
            if self.codebook_class.codebook.version != self.codebook_version:
                raise Exception(
                    f"Saved weights version ({self.codebook_version}) does not match the "\
                    f"codebook version ({self.codebook_class.codebook.version}). "\
                    "Please download the latest weights from https://huggingface.co/relaxml")

            Qidxs_dev = self.Qidxs.device
            self.Qidxs = self.Qidxs.cpu()
            split_qidxs = self.codebook_class.maybe_unpack_idxs(self.Qidxs)
            self.Qidxs_list = []
            for i in range(len(split_qidxs)):
                self.register_buffer(f'Qidxs_{i}', split_qidxs[i].to(Qidxs_dev))
                exec(f'self.Qidxs_list.append(self.Qidxs_{i})')
            del self.Qidxs

            # fuse Wscale into SV
            self.SV *= self.Wscale
            del self.Wscale
            
            self.built_codebook_class = True

        if self.outlier_channel_split:
            input = input[..., self.ocs_dupe_inds]

        result = self.codebook_class(input,
                                     self.Qidxs_list,
                                     self.SU,
                                     self.SV,
                                     self.had_left,
                                     self.had_right,
                                     self.K_left,
                                     self.K_right,
                                     rank=self.rank,
                                     A=self.A,
                                     B=self.B,
                                     rescale_WH=self.rescale_WH,
                                     scaleWH=self.scaleWH,
                                     packed=self.packed,
                                     resid_scale_override=self.resid_scale_override).to(input.dtype)
        if self.has_bias:
            return result + self.bias
        return result
        
