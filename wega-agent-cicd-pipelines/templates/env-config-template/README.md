# Environment Configuration Template

Copy the `config/` folder to your service repository root.

## Folder Structure

```
wega-brd/                    # Your service repo
├── source/
│   └── ...
└── config/                  # ← Copy this folder
    ├── common.yaml          # All clouds, all environments
    ├── secrets.yaml         # Secret references
    ├── gcp/
    │   ├── common.yaml      # GCP all environments
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    ├── azure/
    │   ├── common.yaml      # Azure all environments
    │   ├── dev.yaml
    │   ├── qa.yaml
    │   ├── staging.yaml
    │   └── prod.yaml
    └── aws/
        ├── common.yaml      # AWS all environments
        ├── dev.yaml
        ├── qa.yaml
        ├── staging.yaml
        └── prod.yaml
```

## Quick Start

1. Copy `config/` folder to your repo root
2. Update `config/common.yaml` with your service name
3. Update environment files with your service's values
4. Add secret references to `config/secrets.yaml`
5. Commit and push

## Merge Order

```
common.yaml → {cloud}/common.yaml → {cloud}/{env}.yaml + secrets.yaml
```

## Adding New Variables

- **All clouds, all envs**: Edit `config/common.yaml`
- **One cloud, all envs**: Edit `config/{cloud}/common.yaml`
- **One cloud, one env**: Edit `config/{cloud}/{env}.yaml`
- **New secret**: Edit `config/secrets.yaml` + request DevOps to create in cloud
