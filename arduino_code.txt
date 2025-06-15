int ena = 5;
int in1 = 6;
int in2 = 7;
int in3 = 8;
int in4 = 9;
int enb = 10;

bool runSequence = false;

void setup() {
  Serial.begin(9600);
  pinMode(ena, OUTPUT);
  pinMode(in1, OUTPUT);
  pinMode(in2, OUTPUT);
  pinMode(enb, OUTPUT);
  pinMode(in3, OUTPUT);
  pinMode(in4, OUTPUT);
  stopAllMotors();
}

void loop() {
  // Check for new command
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();

    if (command == "start") {
      runSequence = true;
    } else if (command == "stop") {
      runSequence = false;
      stopAllMotors();
    }
  }

  // Execute motor sequence only once per "start" command
  if (runSequence) {
    // --- Motor A: Run 5 seconds ---
    digitalWrite(in1, HIGH);
    digitalWrite(in2, LOW);
    analogWrite(ena, 255);
    unsigned long startTime = millis();
    while (millis() - startTime < 5000 && runSequence) {
      checkStopSignal();
    }
    digitalWrite(in1, LOW);
    digitalWrite(in2, LOW);

    // --- Motor B: Run 3x (3s ON, 3s OFF) ---
    for (int i = 0; i < 3 && runSequence; i++) {
      digitalWrite(in3, HIGH);
      digitalWrite(in4, LOW);
      analogWrite(enb, 255);
      startTime = millis();
      while (millis() - startTime < 3000 && runSequence) {
        checkStopSignal();
      }

      digitalWrite(in3, LOW);
      digitalWrite(in4, LOW);
      startTime = millis();
      while (millis() - startTime < 3000 && runSequence) {
        checkStopSignal();
      }
    }

    stopAllMotors();
    runSequence = false;
  }
}

void checkStopSignal() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    if (command == "stop") {
      runSequence = false;
      stopAllMotors();
    }
  }
}

void stopAllMotors() {
  digitalWrite(in1, LOW);
  digitalWrite(in2, LOW);
  digitalWrite(in3, LOW);
  digitalWrite(in4, LOW);
  analogWrite(ena, 0);
  analogWrite(enb, 0);
}
