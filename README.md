[<img src="./doc/assets/header-image.png" alt="Rebrowse Hero" width="full"/>](https://rebrowse.me)
[![n0rizkitty](https://img.shields.io/twitter/follow/n0rizkitty?style=social)](https://x.com/n0rizkitty)
<br/>

## About Rebrowse

[Rebrowse]((https://rebrowse.me)) is a powerful tool that converts screen recordings into automated browser workflows.   

## Goal

Most AI copilots are sucks at workflow executions.
They are 
- slow "what takes so much time?"
- not deterministic "you did this yesterday"
- low vilisility "why takes so much time?"
- call LLM everytime "are you stupid?"

I'm solving this issues.

### Remarkable Features

1. 20x Speed and 95% Accuracy
  - we use deterministic executions + customised flash-mode of browser-use.
  - It allows us to execute with 20x speed.

2. The world-first real-time **Preview**/**Evals** of **headless** browser 🙈
  - I used rrweb to ovecome CROS issues.
  - You can interact in real-time with the remote browser deployed under proxy on cloud.

3. Parallel-run(v0.2.0):
[<img src="./doc/assets/parallel-run-mode.png" alt="Rebrowse Hero" width="full"/>](https://rebrowse.me)

## Showcase: Grok-powered X Bot

![X-Bot Demo](./doc/assets/demo-grok-post-hd.gif)

## Demo on prod:   

go to https://app.rebrowse.me

## Repo structure

```bash
rebrowse-app
 L api/ # Web backend server on 127.0.0.1:8000
 L ui/  # Web frontend server on 127.0.0.1:5173
 L extension/ # Rebrowse Recorder Chrome extension.
```

## Installtion Guide

#### **1. Production DB 🌩️** (with Supabase Cloud)
- quick start with shared workflows.
- good for learning how to use.
```bash
# 1. Clone the repository
git clone https://github.com/zk1tty/rebrowse-app.git
cd rebrowse-app

# 2. Update .env with your credentials:
#    - OpenAI API Key: https://platform.openai.com/api-keys
#    - Supabase credentials: https://supabase.com/dashboard

# 3. Start the application
bash docker/setup-docker.sh

# 4. Access the application!
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
```

- **Docker Containers**
<img src="./doc/assets/docker-containers-self-host-mode.png" alt="Docker Containers(prod mode)" width="full"/>

#### **2. Self-Hosting DB 🏠** (with self-hosting Supabase)
- Start with a fresh workflow database.
- good for Entreprise test.
```bash
# 1. Clone the repository
git clone https://github.com/zk1tty/rebrowse-app.git
cd rebrowse-app

# 2. Update .env with your credentials:
#    - OpenAI API Key: https://platform.openai.com/api-keys

# 3. Run setup script with self-hosting flag
bash scripts/setup-docker.sh --self-host

# 4. Access the application!
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# Database Admin: http://localhost:3001
# Database API: http://localhost:8001
```

- **Docker Containers**
<img src="./doc/assets/docker-containers-self-host-mode.png" alt="Docker Containers(self-host mode)" width="full"/>