#define FC_OPEN      2
#define FC_CLOSED    3

#define BTS_RPWM     5
#define BTS_LPWM     6

#define BTS_REN      7
#define BTS_LEN      8

const unsigned long MAX_TRAVEL_TIME = 60000UL;

enum RoofState
{
  UNKNOWN,
  OPENING,
  OPENED,
  CLOSING,
  CLOSED,
  STOPPED,
  ERROR_STATE
};

RoofState state = UNKNOWN;

unsigned long motionStart = 0;

void disableMotor()
{
  analogWrite(BTS_RPWM, 0);
  analogWrite(BTS_LPWM, 0);

  digitalWrite(BTS_REN, LOW);
  digitalWrite(BTS_LEN, LOW);
}

void startOpen()
{
  digitalWrite(BTS_REN, HIGH);
  digitalWrite(BTS_LEN, HIGH);

  analogWrite(BTS_RPWM, 255);
  analogWrite(BTS_LPWM, 0);

  motionStart = millis();

  state = OPENING;
}

void startClose()
{
  digitalWrite(BTS_REN, HIGH);
  digitalWrite(BTS_LEN, HIGH);

  analogWrite(BTS_RPWM, 0);
  analogWrite(BTS_LPWM, 255);

  motionStart = millis();

  state = CLOSING;
}

String getState()
{
  switch (state)
  {
    case OPENING:    return "OPENING";
    case OPENED:     return "OPENED";
    case CLOSING:    return "CLOSING";
    case CLOSED:     return "CLOSED";
    case STOPPED:    return "STOPPED";
    case ERROR_STATE:return "ERROR";
    default:         return "UNKNOWN";
  }
}

void processCommand(String cmd)
{
  cmd.trim();
  cmd.toUpperCase();

  if (cmd == "PING")
  {
    Serial.println("OK");
  }
  else if (cmd == "STATUS")
  {
    Serial.println(getState());
  }
  else if (cmd == "OPEN")
  {
    if (state != OPENED &&
        state != OPENING)
    {
      startOpen();
    }

    Serial.println(getState());
  }
  else if (cmd == "CLOSE")
  {
    if (state != CLOSED &&
        state != CLOSING)
    {
      startClose();
    }

    Serial.println(getState());
  }
  else if (cmd == "STOP")
  {
    disableMotor();

    state = STOPPED;

    Serial.println("STOPPED");
  }
  else
  {
    Serial.println("ERROR");
  }
}

void setup()
{
  pinMode(FC_OPEN, INPUT_PULLUP);
  pinMode(FC_CLOSED, INPUT_PULLUP);

  pinMode(BTS_RPWM, OUTPUT);
  pinMode(BTS_LPWM, OUTPUT);

  pinMode(BTS_REN, OUTPUT);
  pinMode(BTS_LEN, OUTPUT);

  disableMotor();

  Serial.begin(115200);

  delay(1000);

  bool fcOpen =
      digitalRead(FC_OPEN) == HIGH;

  bool fcClosed =
      digitalRead(FC_CLOSED) == HIGH;

  if (fcOpen)
  {
    state = OPENED;
  }
  else if (fcClosed)
  {
    state = CLOSED;
  }
  else
  {
    state = UNKNOWN;
  }

  Serial.print("Etat initial : ");
  Serial.println(getState());
}

void loop()
{
  bool fcOpen =
      digitalRead(FC_OPEN) == HIGH;

  bool fcClosed =
      digitalRead(FC_CLOSED) == HIGH;

  if (state == OPENING && fcOpen)
  {
    disableMotor();

    state = OPENED;

    Serial.println("OPENED");
  }

  if (state == CLOSING && fcClosed)
  {
    disableMotor();

    state = CLOSED;

    Serial.println("CLOSED");
  }

  if ((state == OPENING ||
       state == CLOSING) &&
      millis() - motionStart >
      MAX_TRAVEL_TIME)
  {
    disableMotor();

    state = ERROR_STATE;

    Serial.println("ERROR");
  }

  if (Serial.available())
  {
    String cmd =
      Serial.readStringUntil('\n');

    processCommand(cmd);
  }
}