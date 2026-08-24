# 🌱 ECO-SENTINEL

### AI-Powered Environmental Monitoring & Smart Municipal Waste Management System

**ECO-SENTINEL** is an AI-powered environmental monitoring and waste-detection system designed to transform conventional municipal cleaning vehicles into intelligent environmental monitoring platforms.

Instead of requiring cities to replace their existing fleets with expensive autonomous vehicles, ECO-SENTINEL follows a **retrofit-first approach**. A Raspberry Pi-based AI module, environmental sensors, camera system, live dashboard, and microcontroller can be integrated into an existing municipal vehicle to provide real-time litter detection, pollution monitoring, environmental analysis, and waste-collection assistance.

The project was originally developed for the **TechnoXian World Robotics Championship 2026**.

---

## 🎯 The Problem

Cities face several interconnected environmental-management problems:

* Litter has to be identified and removed efficiently.
* Municipal vehicles usually collect waste without digitally analysing their surroundings.
* Air-quality and smoke conditions may not be monitored continuously at street level.
* Environmental data and waste data are often collected through separate systems.
* Deploying entirely new autonomous smart-cleaning fleets can be expensive.
* Existing municipal vehicles represent infrastructure that could instead be upgraded.

ECO-SENTINEL explores a different approach:

> **Make existing municipal infrastructure intelligent instead of replacing it.**

---

# 🚛 Core Concept

ECO-SENTINEL combines:

**Computer Vision + Environmental Sensors + Edge AI + Robotics + Data Analysis + Municipal Infrastructure**

The prototype is implemented as a four-wheel rover representing a municipal cleaning vehicle.

A camera continuously observes the environment while a Raspberry Pi performs AI inference locally. At the same time, an Arduino collects environmental sensor readings.

The system combines this information to determine the environmental condition of the monitored area and assist with waste collection.

### Basic System Flow

**Camera & Sensors**
↓
**Environmental Data Collection**
↓
**Raspberry Pi Edge AI Processing**
↓
**Real-Time Waste Detection**
↓
**Environmental Action Priority Analysis**
↓
**Operator Dashboard**
↓
**Waste Collection / Environmental Action**
↓
**Session Report**

---

# 🧠 AI Waste Detection

ECO-SENTINEL uses a custom-trained **YOLO object-detection model** for identifying litter.

The model was trained using approximately **1,900 images from the TACO litter dataset**.

### Detection Categories

The system can recognise waste categories including:

* Plastic
* Paper
* Metal
* Glass
* Cardboard
* Other waste

The trained model achieved approximately:

* **70%+ mAP50**
* Approximately **6–7 FPS** on Raspberry Pi 4
* Model size of approximately **5 MB**

The model was optimized for edge deployment so that detection can occur directly on the Raspberry Pi without depending on cloud AI services.

---

# ⚡ Edge AI

One of ECO-SENTINEL's main design principles is **local processing**.

The Raspberry Pi performs the computer-vision workload directly on the vehicle.

The AI stack uses:

* YOLOv11n
* NCNN optimized inference
* OpenCV
* Python

Exporting the model to **NCNN** allows it to run more efficiently on ARM-based Raspberry Pi hardware.

This architecture reduces dependence on continuous internet connectivity and demonstrates how AI can be deployed directly at the edge.

---

# 📷 Ground-Zone Detection

Detecting every object visible to the camera could produce misleading environmental statistics.

For example, litter visible far away should not necessarily be considered waste immediately reachable by the vehicle.

ECO-SENTINEL therefore implements **Ground-Zone Logic**.

Only detections located within approximately the **bottom 60% of the camera frame** are counted as relevant ground-level waste.

This creates a virtual detection region representing the area that the vehicle is currently monitoring.

---

# 📡 Radar-Style Camera Scanning

The camera is mounted on a servo mechanism that allows it to scan the surrounding area.

This provides a radar-like scanning behaviour instead of relying exclusively on a fixed forward-facing camera.

The Raspberry Pi can communicate scanning commands to the Arduino, which controls the physical servo movement.

This allows the vision system to inspect a larger area around the vehicle.

---

# 🌫️ Environmental Monitoring

ECO-SENTINEL does more than detect litter.

It simultaneously monitors environmental conditions using multiple sensors.

### MQ-135

Used for general air-quality monitoring and detection of potentially harmful gases.

### MQ-2

Used for detecting smoke and combustible gases.

### DHT11

Measures:

* Temperature
* Humidity

These readings are transmitted from the Arduino to the Raspberry Pi and integrated into the main environmental dashboard.

---

# 📊 Environmental Action Priority — EAP

A major feature of ECO-SENTINEL is the **Environmental Action Priority (EAP)** system.

Instead of simply displaying raw sensor values, ECO-SENTINEL combines environmental information into an overall priority score.

### EAP Score

**0–100**

The score takes multiple factors into account, including:

* Detected waste
* Waste concentration / coverage
* Air-quality conditions
* Smoke or gas detection

The goal is to help determine **how urgently a particular location requires environmental action**.

Rather than treating every monitored location equally, areas with more serious environmental conditions can be prioritized.

---

# 🖥️ Live Environmental Dashboard

ECO-SENTINEL includes a real-time dashboard that provides operators with a visual overview of the system.

The dashboard can display information such as:

* Live camera stream
* AI waste detections
* Waste count
* Waste categories
* Air-quality readings
* Smoke/gas readings
* Temperature
* Humidity
* EAP score
* Session information
* System status

The dashboard is built using:

* HTML
* CSS
* JavaScript
* Flask

Because the dashboard is served through the Raspberry Pi, it can be viewed from multiple devices on the network.

This includes:

* 📱 Phones
* 💻 Laptops
* 🖥️ 7-inch onboard display

---

# 🗑️ Physical Waste Collection

ECO-SENTINEL is not limited to detecting environmental problems.

The prototype contains a **servo-operated scooper mechanism** capable of physically interacting with and collecting waste.

The AI system identifies waste and provides environmental intelligence, while the robotic hardware demonstrates how detection can ultimately lead to physical action.

The prototype therefore demonstrates the complete concept:

**Detect → Analyse → Prioritize → Collect → Report**

---

# 🔌 Dual-Controller Architecture

ECO-SENTINEL separates high-level computing from real-time hardware control.

## Raspberry Pi 4 — High-Level Controller

The Raspberry Pi handles:

* AI inference
* Computer vision
* YOLO detection
* OpenCV processing
* Dashboard server
* Video streaming
* Environmental analysis
* EAP calculation
* Session statistics
* Communication with Arduino
* Reporting

## Arduino Uno — Hardware Controller

The Arduino handles:

* Environmental sensors
* Servo control
* Camera scanning
* Scooper control
* Hardware-level operations
* Communication with Raspberry Pi

The two controllers communicate using **UART serial communication at 9600 baud**.

### Architecture

```text
                    ┌──────────────────────┐
                    │      PI CAMERA       │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   RASPBERRY PI 4     │
                    │                      │
                    │  YOLO / NCNN         │
                    │  OpenCV              │
                    │  Flask               │
                    │  EAP Engine          │
                    │  Dashboard           │
                    │  Reporting           │
                    └──────────┬───────────┘
                               │
                            UART
                          9600 baud
                               │
                               ▼
                    ┌──────────────────────┐
                    │     ARDUINO UNO      │
                    └─────┬────┬────┬─────┘
                          │    │    │
                ┌─────────┘    │    └──────────┐
                ▼              ▼               ▼
          ENVIRONMENTAL      SERVOS          MOTORS /
             SENSORS         & SCOOP          CONTROL
```

---

# 🔧 Hardware

The ECO-SENTINEL prototype uses:

| Component                   | Purpose                        |
| --------------------------- | ------------------------------ |
| Raspberry Pi 4 4GB          | Main AI and computing platform |
| Arduino Uno                 | Sensor and hardware controller |
| Raspberry Pi Camera         | Computer vision                |
| Camera Servo                | Radar-style scanning           |
| MQ-135                      | Air-quality monitoring         |
| MQ-2                        | Smoke/gas detection            |
| DHT11                       | Temperature and humidity       |
| 7-inch Display              | Onboard dashboard              |
| FS-i6 6-Channel Transmitter | Manual rover control           |
| Brushed ESC                 | Motor control                  |
| 12V Motors                  | Rover movement                 |
| Servo Motors                | Camera and scooper mechanisms  |
| Metal Chassis               | Two-level prototype platform   |

---

# 💻 Software Stack

### Raspberry Pi

* Raspberry Pi OS
* Python
* OpenCV
* YOLOv11n
* NCNN
* Flask
* PySerial

### Web Interface

* HTML
* CSS
* JavaScript

### Arduino

* Arduino C/C++
* UART Serial Communication
* Sensor interfaces
* Servo control

---

# 🔄 Communication System

The Raspberry Pi and Arduino continuously exchange information through serial communication.

### Arduino → Raspberry Pi

The Arduino transmits environmental information including:

```text
Air Quality
Smoke / Gas
Temperature
Humidity
Sensor Status
```

### Raspberry Pi → Arduino

The Raspberry Pi can send commands relating to:

```text
Camera Scanning
Servo Position
Control Actions
System Commands
```

This separation makes the architecture modular.

The Raspberry Pi concentrates on computationally intensive tasks while the Arduino handles physical hardware and sensor interaction.

---

# 📈 Session Monitoring

ECO-SENTINEL can track environmental information over an operating session.

A session can contain information such as:

* Total litter detected
* Waste categories
* Environmental readings
* EAP score
* Area condition
* Detection statistics

At the end of a monitoring session, the operator can review the collected information.

The system supports a **save / redo workflow**, allowing an environmental scan to be repeated when required.

---

# 📧 Automated Reporting

Environmental information collected during a session can be converted into a report.

ECO-SENTINEL was designed to support automatic delivery of these reports to a configured municipal or monitoring authority email address.

This demonstrates how the system could become more than a cleaning robot.

A fleet of upgraded vehicles could potentially function as **mobile environmental data-collection nodes**.

---

# 🚛 Retrofit Philosophy

One of the most important ideas behind ECO-SENTINEL is that a smart city does not necessarily require replacing all existing infrastructure.

Instead of:

```text
Existing Municipal Truck
        ↓
     Discard
        ↓
Purchase Expensive Smart Vehicle
```

ECO-SENTINEL proposes:

```text
Existing Municipal Truck
        +
Camera
        +
Raspberry Pi Edge AI
        +
Environmental Sensors
        +
Operator Dashboard
        ↓
AI-Assisted Municipal Vehicle
```

This potentially lowers the barrier to introducing environmental intelligence into existing fleets.

---

# 🌍 Potential Real-World Deployment

A production version of ECO-SENTINEL could be mounted onto municipal:

* Garbage collection trucks
* Street-cleaning vehicles
* Waste-management vehicles
* Environmental inspection vehicles

As these vehicles travel through a city, they could simultaneously collect environmental information.

Multiple equipped vehicles could eventually form a distributed monitoring network.

```text
Vehicle 01 ─┐
Vehicle 02 ─┤
Vehicle 03 ─┼──► Environmental Monitoring System
Vehicle 04 ─┤
Vehicle 05 ─┘
```

This could provide authorities with street-level environmental information while using vehicles that already travel throughout the city.

---

# 🚀 Future Development

ECO-SENTINEL is currently a prototype and research platform.

Potential future development includes:

* Improved AI detection models
* Larger and more diverse training datasets
* GPS integration
* Environmental heatmaps
* Geographic waste mapping
* Improved air-quality sensors
* Automatic route prioritization
* Fleet-wide data aggregation
* Improved edge-AI accelerators
* Multiple-camera coverage
* Automated waste collection
* Autonomous navigation
* Integration with real municipal vehicles
* Centralized environmental analytics

The current operator-assisted system could therefore serve as a foundation for progressively more autonomous municipal environmental vehicles.

---

# ✨ Key Features

* 🤖 Real-time AI litter detection
* 🧠 Raspberry Pi edge inference
* 📦 YOLOv11n + NCNN optimization
* 📷 Servo-controlled scanning camera
* 🌫️ Air-quality monitoring
* 🔥 Smoke/gas detection
* 🌡️ Temperature monitoring
* 💧 Humidity monitoring
* 📊 Environmental Action Priority scoring
* 🖥️ Live web dashboard
* 📱 Multi-device dashboard access
* 🗑️ Servo-operated waste scooper
* 🔌 Raspberry Pi + Arduino architecture
* 📈 Session statistics
* 📧 Environmental reporting
* 🚛 Retrofit-oriented municipal design
* 🌐 Expandable fleet architecture

---

# 🏆 Project Background

ECO-SENTINEL was developed as a robotics and environmental technology project for the **TechnoXian World Robotics Championship 2026**.

The prototype demonstrates that a relatively compact edge-computing platform can combine computer vision, robotics, environmental sensing, web technologies, and physical waste collection into a single integrated system.

The long-term idea behind ECO-SENTINEL is simple:

> **A municipal vehicle should not only clean a city — it can understand the environment around it.**

---

# 🌱 Vision

ECO-SENTINEL explores a future where ordinary municipal vehicles become intelligent environmental nodes.

Instead of environmental monitoring being performed only by fixed stations, vehicles already moving through streets could continuously observe waste conditions, measure environmental parameters, identify priority areas, and provide authorities with actionable data.

**Detect. Monitor. Prioritize. Act.**

That is the core idea behind **ECO-SENTINEL**.
