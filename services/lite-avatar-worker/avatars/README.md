# Avatars

Place LiteAvatar avatar data folders here. Each subfolder is one avatar
and must contain the data files required by `lite_avatar.py` upstream
(image, mesh, etc.).

**Do not commit avatar data files** — they are large binaries. Only the
folder structure + this README are tracked.

Download avatars from the
[LiteAvatarGallery](https://modelscope.cn/models/HumanAIGC-Engineering/LiteAvatarGallery)
and arrange like:

```
avatars/
├── linh_female/
├── nam_male/
├── huong_female/
├── tuan_male/
└── mai_female/
```

The folder names must match `LiteAvatarProvider.AVAILABLE_AVATARS` in
`apps/workers/dh_providers/liteavatar.py`.
