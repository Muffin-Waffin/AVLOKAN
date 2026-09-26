"""Small checkpoint-compatible transformer blocks from the official BIT-CD model."""
import torch
from torch import nn


class Residual(nn.Module):
    def __init__(self, fn):
        super().__init__(); self.fn = fn
    def forward(self, x, **kwargs):
        return self.fn(x, **kwargs) + x


class Residual2(nn.Module):
    def __init__(self, fn):
        super().__init__(); self.fn = fn
    def forward(self, x, x2, **kwargs):
        return self.fn(x, x2, **kwargs) + x


class PreNorm(nn.Module):
    def __init__(self, dim, fn):
        super().__init__(); self.norm = nn.LayerNorm(dim); self.fn = fn
    def forward(self, x, **kwargs):
        return self.fn(self.norm(x), **kwargs)


class PreNorm2(nn.Module):
    def __init__(self, dim, fn):
        super().__init__(); self.norm = nn.LayerNorm(dim); self.fn = fn
    def forward(self, x, x2, **kwargs):
        return self.fn(self.norm(x), self.norm(x2), **kwargs)


class FeedForward(nn.Module):
    def __init__(self, dim, hidden_dim, dropout=0.0):
        super().__init__(); self.net = nn.Sequential(
            nn.Linear(dim, hidden_dim), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, dim), nn.Dropout(dropout))
    def forward(self, x): return self.net(x)


class Cross_Attention(nn.Module):
    def __init__(self, dim, heads=8, dim_head=64, dropout=0.0, softmax=True):
        super().__init__(); inner = dim_head * heads; self.heads = heads
        self.scale = dim ** -0.5; self.softmax = softmax
        self.to_q = nn.Linear(dim, inner, bias=False)
        self.to_k = nn.Linear(dim, inner, bias=False)
        self.to_v = nn.Linear(dim, inner, bias=False)
        self.to_out = nn.Sequential(nn.Linear(inner, dim), nn.Dropout(dropout))
    def forward(self, x, m, mask=None):
        b, n, _ = x.shape; h = self.heads
        q, k, v = (self.to_q(x), self.to_k(m), self.to_v(m))
        q = q.reshape(b, n, h, -1).permute(0, 2, 1, 3)
        k = k.reshape(b, m.shape[1], h, -1).permute(0, 2, 1, 3)
        v = v.reshape(b, m.shape[1], h, -1).permute(0, 2, 1, 3)
        dots = torch.einsum("bhid,bhjd->bhij", q, k) * self.scale
        if self.softmax: dots = dots.softmax(dim=-1)
        out = torch.einsum("bhij,bhjd->bhid", dots, v).permute(0, 2, 1, 3).reshape(b, n, -1)
        return self.to_out(out)


class Attention(nn.Module):
    def __init__(self, dim, heads=8, dim_head=64, dropout=0.0):
        super().__init__(); inner = dim_head * heads; self.heads = heads
        self.scale = dim ** -0.5
        self.to_qkv = nn.Linear(dim, inner * 3, bias=False)
        self.to_out = nn.Sequential(nn.Linear(inner, dim), nn.Dropout(dropout))
    def forward(self, x, mask=None):
        b, n, _ = x.shape; h = self.heads
        q, k, v = self.to_qkv(x).chunk(3, dim=-1)
        q, k, v = [t.reshape(b, n, h, -1).permute(0, 2, 1, 3) for t in (q, k, v)]
        dots = torch.einsum("bhid,bhjd->bhij", q, k) * self.scale
        attn = dots.softmax(dim=-1)
        out = torch.einsum("bhij,bhjd->bhid", attn, v).permute(0, 2, 1, 3).reshape(b, n, -1)
        return self.to_out(out)


class Transformer(nn.Module):
    def __init__(self, dim, depth, heads, dim_head, mlp_dim, dropout):
        super().__init__(); self.layers = nn.ModuleList([])
        for _ in range(depth):
            self.layers.append(nn.ModuleList([
                Residual(PreNorm(dim, Attention(dim, heads=heads, dim_head=dim_head, dropout=dropout))),
                Residual(PreNorm(dim, FeedForward(dim, mlp_dim, dropout=dropout))) ]))
    def forward(self, x, mask=None):
        for attn, ff in self.layers: x = ff(attn(x, mask=mask))
        return x


class TransformerDecoder(nn.Module):
    def __init__(self, dim, depth, heads, dim_head, mlp_dim, dropout, softmax=True):
        super().__init__(); self.layers = nn.ModuleList([])
        for _ in range(depth):
            self.layers.append(nn.ModuleList([
                Residual2(PreNorm2(dim, Cross_Attention(dim, heads=heads, dim_head=dim_head, dropout=dropout, softmax=softmax))),
                Residual(PreNorm(dim, FeedForward(dim, mlp_dim, dropout=dropout))) ]))
    def forward(self, x, m):
        for attn, ff in self.layers: x = ff(attn(x, m))
        return x


class TwoLayerConv2d(nn.Sequential):
    def __init__(self, in_channels, out_channels, kernel_size=3):
        super().__init__(nn.Conv2d(in_channels, in_channels, kernel_size, padding=kernel_size // 2, bias=False),
                         nn.BatchNorm2d(in_channels), nn.ReLU(),
                         nn.Conv2d(in_channels, out_channels, kernel_size, padding=kernel_size // 2))
