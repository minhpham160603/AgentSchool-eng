<p align="center">
  <img src="./static/logo.png" width="280" alt="Epitome Logo">
</p>

<h1 align="center">Epitome</h1>

<p align="center">
  <strong>Start AI Pilot platform for social science integration</strong>
</p>

<p align="center">
  <a href="./README.md">🌍 English</a> •
  <a href="./README_ZH.md">🇨🇳 Chinese</a> •
  <a href="https://arxiv.org/abs/2507.01061">📄 arXiv</a> •
  <a href="https://www.epitome-ai.com/">🌐 Network of officials</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/JDK-1.8+-orange.svg" alt="JDK">
  <img src="https://img.shields.io/badge/Spring%20Boot-2.7.3-brightgreen.svg" alt="Spring Boot">
  <img src="https://img.shields.io/badge/MySQL-8.x-blue.svg" alt="MySQL">
  <img src="https://img.shields.io/badge/Redis-Latest-red.svg" alt="Redis">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## 📖 Contents

- [Project Profile](#-Project Profile)
- [Core characteristics](#-Core characteristics)
- [Technical architecture](#-Technical architecture)
- [Environmental requirements](#-Environmental requirements)
- [Fast start](#-Fast start)
- [Project structure](#-Project structure)
- [Configure Guide](#-Configure Guide)
- [Other](#-Other)
- [Open Source Licence](#-Open Source Licence)
- [Contact us](#-Contact us)
- [References](#-References)

---

## 🎯 Project Profile

**Epitome** It's the first experimental open platform around the world to focus on the deep integration of artificial intelligence with social science**Experimental intervention-Experimental environment-Pilot participants**Full-process intelligence helps researchers to easily design and run complex human-engineer interactive experiment scenarios, achieve systematic research and the exploration of integrated solutions to the social impact of artificial intelligence, and advance the more harmonious integration of artificial intelligence into human society。

### 🎓 Apply scene

- Experimental studies in social sciences
- Human interaction behaviour analysis
- AI Social impact assessment
- Group dynamics simulation
- Interdisciplinary experimental design

---

## ✨ Core characteristics

### 🎭 Innovative interactive scenes

#### A role-playing robot
- 🤖 Model judges, historical figures, diverse social roles
- 🌐 Experiment to achieve dialogue across time and space and between identities
- 📊 Providing standardized and repeatable interactive elements for abstract social studies

#### Mixed chat room
- 👥 Support"People-People-Machine-Machine"Multiple interactive modes
- 🔄 Simulation of complex social networks and community interactions
- 🔬 Potential for innovation in the study of group behaviour and social dynamics

#### Social Simulation
- 💼 Through smart bodies Agent Simulation of human economic transactions, social conflicts, etc
- ⏱️ Provides a large-scale, long-term simulation of social conditions
- 💰 Study to achieve low-cost policy impact prediction and social normative evolution


### 🔄 Full process closed loop support

- **🎯 Experimental management**：Full life cycle management from design to implementation
- **📦 Material management**：Centralized management of multimodular experimental material
- **📋 Questionnaire management**：Flexible questionnaire design and data collection
- **⚙️ Workflow management**：Visualization of modular components
- **📈 Data analysis**：Real-time data acquisition and export function


### 🔓 Open research design

#### Diversity Support
- 📝 Text, Picture, Video
- 📄 PDF、PPT Waiting for multiple formats
- 🤖 Multimodular Large Model Support Experimental Material Preparation

#### Open architecture design
- 🔧 Workflow Custom Design
- 🧩 Agent System flexibility
- 🎨 Compatible multidisciplinary and complex experimental paradigm


### 🎮 Controlled experimental propulsion

- **🔍 The scale of the experiment can be expanded**：Grounds and personnel restrictions to break down traditional underground experiments
- **⚡ Accurate process control**：Preset interactive processes, balancing controls with reality simulations
- **♻️ Repeatability enhancement**：Standardized experimental processes to improve replicability and verifiability
- **📊 Real-time data collection**：Record experimental data throughout the process to support multi-dimensional analysis

---

## 🏗️ Technical architecture

### Core technology warehouse

| category | Technical Selection | Version |
|------|---------|------|
| **Core framework** | Spring Boot | 2.7.3 |
| **Persistence Layer** | MyBatis-Plus | - |
| **Database** | MySQL | 8.x |
| **Cache** | Redis (Jedis) | - |
| **Security framework** | Apache Shiro | - |
| **Session Sharing** | Shiro-Redis | - |
| **API Document** | Knife4j (Swagger) | - |
| **Excel processing** | EasyExcel, EasyPoi | - |
| **File Storage** | MinIO | - |
| **Real-time communications** | WebSocket | - |
| **Library** | Hutool, FastJSON, Druid | - |

---

## 📋 Environmental requirements

### Necessary environment

- ☕ **JDK**: 1.8+
- 📦 **Maven**: 3.x
- 🗄️ **MySQL**: 8.x
- 🔴 **Redis**: 5.x+

---

## 🚀 Fast start

### Steps 1: Cloning and construction projects

```bash
# Cloning warehouse
git clone https://github.com/your-org/epitome.git

# Enter Project Directory
cd epitome

# Install dependency and pack (including local) lib Dependency）
mvn clean install -DskipTests
```

### Steps 2: Modify Profile

Main Configuration`src/main/resources/application.yml`：

Active Profile Yes `application.yml` Adopted `spring.profiles.active` Assign (e. g `testLocal`）
```yaml
spring:
  profiles:
    active: testLocal  # Select Active Environment Configuration
```

Counterpart Profile Environment profile (e.g.) `application-testLocal.yml`）Medium Configuration：
  - **MySQL**：`spring.datasource.url / username / password`
  - **Redis**：`spring.redis.host / port` Wait

```yaml
spring:
  datasource:
    url: jdbc:mysql://{your_mysql_ip}:3306/ailab?useSSL=false&characterEncoding=utf8
    username: {your_mysql_username}
    password: {your_mysql_password}
    
  redis:
    host: {your_redis_ip}
    port: 6379
    password: {your_redis_password}
```

> 💡 **Hint**: Will `{your_mysql_ip}` Replace placeholder with actual value

### Steps 3: Run Item

Use Maven Run

```bash
# Use Maven Run (use current active) profile）
mvn spring-boot:run

# Or pack and run
mvn clean package -DskipTests
java -jar target/ailab-1.0.0.jar
```

Default ports profile Configure (as used locally) 8085）。

### Steps 4: Verify startup

Visits Knife4j Document Validation Service Started Normally (Performance) context-path Reference）：

- 📚 **API Document Example**: `http://localhost:8085/doc.html`

---

## 📁 Project structure

```
src/
└── main/
    ├── java/com/nbtech/ailab/
    │   ├── AiLabApplication.java           # 🚀 Start Class
    │   ├── biz/                             # 💼 Operational level
    │   │   ├── controller/                  # 🎮 controller
    │   │   ├── dao/                         # 🗄️ Data Access Layer
    │   │   ├── dto/                         # 📦 Data Transfer Object
    │   │   ├── entity/                      # 📋 Entity category
    │   │   └── service/                     # ⚙️ Service level
    │   ├── common/                          # 🔧 Public Modules
    │   ├── config/                          # ⚙️ Configure Classes
    │   ├── facade/                          # 🎭 The front/Syndication services
    │   ├── security/                        # 🔒 Security Configuration
    │   ├── util/                            # 🛠️ Tool class
    │   ├── vo/                              # 👁️ View Objects
    │   └── websocket/                       # 🔌 WebSocket
    └── resources/                           # SQL Script and Change Record
        └── mapper/                          # MyBatis Map File
```

## ⚙️ Configure Guide

- **Multi-environment**：Pass `spring.profiles.active` Switch (e. g.) `testLocal`、`testDev`、`formalDev`）。
- **Uploading files**：Yes `application.yml` It's configured `spring.servlet.multipart`（Like 500MB Limits）。
- **Database**：Use MyBatis-Plus，Logically delete fields as `is_deleted`。
---

## 🐳 Other
- Local Dependencies：`lib/common-0.0.1-release.jar`，Existence and installed or adopted `system` Scope in。
- Deployment: provided within the project `Dockerfile`，Mirror deployment as required。

---

## 📄 Open Source Licence

Use of this project [MIT](https://opensource.org/licenses/MIT) Licence。

```
MIT License

Copyright (c) 2025 Epitome Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 📞 Contact us

If you're interested in this platform or have a need for social experiments, you're welcome to contact us through：

### 📧 Contact Mailbox
**epitome_AI4SS@163.com**

### 💬 Social media

<table>
  <tr>
    <td align="center">
      <strong>We believe in the public domain</strong><br>
      <img src="./static/WeChatOfficialAccount.jpg" width="150"><br>
      <sub>Epitome-AI</sub>
    </td>
    <td align="center">
      <strong>Bilibili</strong><br>
      <img src="./static/Bilibili.jpg" width="150"><br>
      <sub>Watch our video dynamics</sub>
    </td>
    <td align="center">
      <strong>Little Red</strong><br>
      <img src="./static/RedNotes.jpg" width="150"><br>
      <sub>View Recent Sharing</sub>
    </td>
  </tr>
</table>

### 🌐 Online resources

- 🏠 **Official website**: [https://www.epitome-ai.com/](https://www.epitome-ai.com/)
- 📄 **Research papers**: [arXiv:2507.01061](https://arxiv.org/abs/2507.01061)
- 💻 **GitHub**: [https://github.com/your-org/epitome](https://github.com/epitome-AISS/epitome)

---

## 📖 References

If you use it in your research, Epitome Platform, please quote our paper：

```bibtex
@misc{qu2025epitomepioneeringexperimentalplatform,
  title={Epitome: Pioneering an Experimental Platform for AI-Social Science Integration}, 
  author={Jingjing Qu and Kejia Hu and Jun Zhu and Yulei Ye and Wenhao Li and Teng Wang and Zhiyun Chen and Chaochao Lu and Aimin Zhou and Xiangfeng Wang and Xia Hu and James Evans},
  year={2025},
  eprint={2507.01061},
  archivePrefix={arXiv},
  primaryClass={cs.CY},
  url={https://arxiv.org/abs/2507.01061}
}
```

---

<p align="center">
  <sub>Built with ❤️ by Epitome Team</sub>
</p>

<p align="center">
  <sub>© 2025 Epitome. All rights reserved.</sub>
</p>
