/*
 * RoofController - controle du toit roulant de l'observatoire
 * ===========================================================
 *
 * Firmware du controleur Arduino (Uno / Nano, ATmega328P).
 * Materiel : moteur 12 V reducte, driver BTS7960, deux fins de course NF.
 *
 * Principes
 * ---------
 * 1. La boucle principale NE BLOQUE JAMAIS : pas de delay(), pas de
 *    String, pas de readStringUntil(). Une commande serie ne peut donc
 *    jamais retarder l'arret sur fin de course.
 * 2. Les fins de course sont lu a chaque iteration et priment sur tout :
 *    atteindre la butee coupe le moteur immediatement, sans rampe.
 * 3. Tout defaut coupe le moteur et fige l'etat en ERROR. Seule une
 *    commande STOP explicite efface le defaut.
 * 4. Le firmware est l'autorite en matiere de securite. Le serveur ne fait
 *    que demander des mouvements et lire l'etat.
 *
 * Protocole serie (une ligne ASCII par message, termine par \n)
 * -------------------------------------------------------------
 * Commandes recues :
 *   PING     -> etat courant
 *   STATUS   -> etat courant
 *   OPEN     -> demarre l'ouverture
 *   CLOSE    -> demarre la fermeture
 *   STOP     -> coupe le moteur, fige STOPPED, efface un eventuel defaut
 *
 * Reponses :
 *   OK:<ETAT>            commande acceptee
 *   ER:<CODE>:<ETAT>     commande refusee (CODE = BUSY, FAULT, UNKNOWN_CMD,
 *                        LINE_TOO_LONG)
 *
 * Messages asynchrones (jamais en reponse a une commande) :
 *   EVT:<QUOI>:<ETAT>    BOOT, OPENED, CLOSED, TIMEOUT, NO_MOTION, LIMITS
 *
 * ETAT vaut : UNKNOWN, OPENING, OPENED, CLOSING, CLOSED, STOPPED, ERROR.
 * Tout message se termine donc par l'etat courant, ce qui permet au serveur
 * de le lire sans connaitre le detail du protocole.
 */

#include "roof_config.h"

/* -- Verification du brochage -------------------------------------------
 *
 * Faite a la compilation : une configuration incoherente ne peut pas etre
 * televersee. L'interface ne propose que des broches valides, mais le fichier
 * de configuration reste modifiable a la main.
 */

#define ROOF_PIN_BIT(p) (1UL << (p))

#if (PIN_LIMIT_OPEN < 2) || (PIN_LIMIT_OPEN > 19)
#error "La butee d'ouverture doit etre sur D2..D13 ou A0..A5"
#endif

#if (PIN_LIMIT_CLOSED < 2) || (PIN_LIMIT_CLOSED > 19)
#error "La butee de fermeture doit etre sur D2..D13 ou A0..A5"
#endif

#if (PIN_BTS_REN < 2) || (PIN_BTS_REN > 19)
#error "R_EN doit etre sur D2..D13 ou A0..A5"
#endif

#if (PIN_BTS_LEN < 2) || (PIN_BTS_LEN > 19)
#error "L_EN doit etre sur D2..D13 ou A0..A5"
#endif

#if (PIN_BTS_RPWM != 3) && (PIN_BTS_RPWM != 5) && (PIN_BTS_RPWM != 6) && \
    (PIN_BTS_RPWM != 9) && (PIN_BTS_RPWM != 10) && (PIN_BTS_RPWM != 11)
#error "RPWM doit etre une broche PWM : D3, D5, D6, D9, D10 ou D11"
#endif

#if (PIN_BTS_LPWM != 3) && (PIN_BTS_LPWM != 5) && (PIN_BTS_LPWM != 6) && \
    (PIN_BTS_LPWM != 9) && (PIN_BTS_LPWM != 10) && (PIN_BTS_LPWM != 11)
#error "LPWM doit etre une broche PWM : D3, D5, D6, D9, D10 ou D11"
#endif

#if ((ROOF_PIN_BIT(PIN_LIMIT_OPEN) & ROOF_PIN_BIT(PIN_LIMIT_CLOSED)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_OPEN) & ROOF_PIN_BIT(PIN_BTS_RPWM)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_OPEN) & ROOF_PIN_BIT(PIN_BTS_LPWM)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_OPEN) & ROOF_PIN_BIT(PIN_BTS_REN)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_OPEN) & ROOF_PIN_BIT(PIN_BTS_LEN)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_CLOSED) & ROOF_PIN_BIT(PIN_BTS_RPWM)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_CLOSED) & ROOF_PIN_BIT(PIN_BTS_LPWM)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_CLOSED) & ROOF_PIN_BIT(PIN_BTS_REN)) || \
     (ROOF_PIN_BIT(PIN_LIMIT_CLOSED) & ROOF_PIN_BIT(PIN_BTS_LEN)) || \
     (ROOF_PIN_BIT(PIN_BTS_RPWM) & ROOF_PIN_BIT(PIN_BTS_LPWM)) || \
     (ROOF_PIN_BIT(PIN_BTS_RPWM) & ROOF_PIN_BIT(PIN_BTS_REN)) || \
     (ROOF_PIN_BIT(PIN_BTS_RPWM) & ROOF_PIN_BIT(PIN_BTS_LEN)) || \
     (ROOF_PIN_BIT(PIN_BTS_LPWM) & ROOF_PIN_BIT(PIN_BTS_REN)) || \
     (ROOF_PIN_BIT(PIN_BTS_LPWM) & ROOF_PIN_BIT(PIN_BTS_LEN)) || \
     (ROOF_PIN_BIT(PIN_BTS_REN) & ROOF_PIN_BIT(PIN_BTS_LEN)))
#error "Deux fonctions utilisent la meme broche"
#endif

/* -- Etats --------------------------------------------------------------- */

enum RoofState : uint8_t {
  ST_UNKNOWN = 0,
  ST_OPENING,
  ST_OPENED,
  ST_CLOSING,
  ST_CLOSED,
  ST_STOPPED,
  ST_ERROR
};

/* Phase physique du moteur. Le sens est porte par `direction`.
 * PH_WAIT existe pour respecter le temps mort entre deux sens : on annonce
 * deja OPENING/CLOSING, mais le moteur ne recoit rien encore. */
enum MotorPhase : uint8_t {
  PH_IDLE = 0,
  PH_WAIT,
  PH_RAMP_UP,
  PH_RUN,
  PH_RAMP_DOWN
};

struct LimitSwitch {
  uint8_t pin;
  bool raw;        /* derniere lecture brute */
  bool stable;     /* etat apres anti-rebond */
  uint32_t changedAt;
};

/* -- Etat global --------------------------------------------------------- */

RoofState state = ST_UNKNOWN;
MotorPhase phase = PH_IDLE;
int8_t direction = 0;      /* +1 ouverture, -1 fermeture, 0 arret */
bool fault = false;        /* defaut actif : plus aucun mouvement permis */

uint16_t pwm = 0;          /* rapport cyclique courant, 0-255 */
uint16_t rampFrom = 0;     /* vitesse au debut de la rampe d'arret */
uint32_t phaseStart = 0;   /* debut de la phase courante */
uint32_t motionStart = 0;  /* debut du mouvement physique reel */
uint32_t lastStop = 0;     /* instant de la derniere coupure moteur */

LimitSwitch swOpen   = { PIN_LIMIT_OPEN,   false, false, 0 };
LimitSwitch swClosed = { PIN_LIMIT_CLOSED, false, false, 0 };

/* Tampon de ligne fixe : aucune allocation dynamique, donc pas de
 * fragmentation du tas sur un microcontroleur qui tourne des mois. */
char lineBuf[ROOF_LINE_MAX + 1];
uint8_t lineLen = 0;
bool lineOverflow = false;

/* -- Moteur -------------------------------------------------------------- */

void writePwm()
{
  if (direction > 0) {
    analogWrite(PIN_BTS_LPWM, 0);
    analogWrite(PIN_BTS_RPWM, pwm);
  } else if (direction < 0) {
    analogWrite(PIN_BTS_RPWM, 0);
    analogWrite(PIN_BTS_LPWM, pwm);
  } else {
    analogWrite(PIN_BTS_RPWM, 0);
    analogWrite(PIN_BTS_LPWM, 0);
  }
}

void enableMotor()
{
  digitalWrite(PIN_BTS_REN, HIGH);
  digitalWrite(PIN_BTS_LEN, HIGH);
}

/* Coupe immediate : PWM a zero AVANT de relacher les validations, pour ne
 * pas laisser le pont actif sur une valeur non nulle. */
void cutMotor()
{
  pwm = 0;
  analogWrite(PIN_BTS_RPWM, 0);
  analogWrite(PIN_BTS_LPWM, 0);
  digitalWrite(PIN_BTS_REN, LOW);
  digitalWrite(PIN_BTS_LEN, LOW);

  direction = 0;
  phase = PH_IDLE;
  lastStop = millis();
}

/* Interpolation lineaire, sans utiliser map() dont le comportement sur les
 * types longs est source d'erreurs. */
uint16_t rampValue(uint32_t elapsed, uint32_t duration, uint16_t from, uint16_t to)
{
  if (duration == 0 || elapsed >= duration) {
    return to;
  }

  long delta = (long)to - (long)from;
  long value = (long)from + (delta * (long)elapsed) / (long)duration;

  if (value < 0) {
    value = 0;
  }

  return (uint16_t)value;
}

/* -- Fins de course ------------------------------------------------------ */

bool readLimit(LimitSwitch &sw)
{
  bool now = (digitalRead(sw.pin) == HIGH);

  if (now != sw.raw) {
    sw.raw = now;
    sw.changedAt = millis();
  }

  if ((millis() - sw.changedAt) >= ROOF_DEBOUNCE_MS) {
    sw.stable = sw.raw;
  }

  return sw.stable;
}

/* A l'amorcage, on ne veut pas attendre le delai d'anti-rebond : l'etat
 * physique doit etre connu tout de suite. */
void initLimit(LimitSwitch &sw)
{
  bool now = (digitalRead(sw.pin) == HIGH);
  sw.raw = now;
  sw.stable = now;
  sw.changedAt = millis();
}

/* -- Messages serie ------------------------------------------------------ */

const char *stateName()
{
  switch (state) {
    case ST_OPENING: return "OPENING";
    case ST_OPENED:  return "OPENED";
    case ST_CLOSING: return "CLOSING";
    case ST_CLOSED:  return "CLOSED";
    case ST_STOPPED: return "STOPPED";
    case ST_ERROR:   return "ERROR";
    default:         return "UNKNOWN";
  }
}

void sendOk()
{
  Serial.print(F("OK:"));
  Serial.println(stateName());
}

void sendError(const __FlashStringHelper *code)
{
  Serial.print(F("ER:"));
  Serial.print(code);
  Serial.print(':');
  Serial.println(stateName());
}

void sendEvent(const __FlashStringHelper *what)
{
  Serial.print(F("EVT:"));
  Serial.print(what);
  Serial.print(':');
  Serial.println(stateName());
}

/* -- Transitions --------------------------------------------------------- */

void finishMotion(RoofState reached)
{
  cutMotor();
  state = reached;
  sendEvent(reached == ST_OPENED ? F("OPENED") : F("CLOSED"));
}

void raiseFault(const __FlashStringHelper *code)
{
  cutMotor();
  fault = true;
  state = ST_ERROR;
  sendEvent(code);
}

/* Sens reel du mouvement, ou 0 si le moteur est a l'arret (y compris
 * pendant une deceleration). */
int8_t movingDirection()
{
  if (phase == PH_WAIT || phase == PH_RAMP_UP || phase == PH_RUN) {
    return direction;
  }
  return 0;
}

void startMotion(int8_t dir)
{
  /* Une deceleration est en cours : on la termine avant de repartir. Le
   * temps mort de changement de sens s'appliquera dans tous les cas. */
  if (phase != PH_IDLE) {
    cutMotor();
  }

  direction = dir;
  pwm = 0;
  state = (dir > 0) ? ST_OPENING : ST_CLOSING;
  phase = PH_WAIT;
  phaseStart = millis();
}

void stopMotion()
{
  if (phase == PH_IDLE) {
    state = ST_STOPPED;
    return;
  }

  if (phase == PH_RAMP_DOWN) {
    return; /* deja en cours */
  }

  rampFrom = pwm;
  phase = PH_RAMP_DOWN;
  phaseStart = millis();
  state = ST_STOPPED;
}

/* -- Commandes ----------------------------------------------------------- */

void handleOpen()
{
  if (fault) {
    sendError(F("FAULT"));
    return;
  }

  int8_t moving = movingDirection();

  if (moving > 0) {
    sendOk();                       /* deja en ouverture : idempotent */
    return;
  }

  if (moving < 0) {
    sendError(F("BUSY"));           /* fermeture en cours : STOP d'abord */
    return;
  }

  if (readLimit(swOpen)) {
    state = ST_OPENED;
    sendOk();
    return;
  }

  startMotion(+1);
  sendOk();
}

void handleClose()
{
  if (fault) {
    sendError(F("FAULT"));
    return;
  }

  int8_t moving = movingDirection();

  if (moving < 0) {
    sendOk();                       /* deja en fermeture */
    return;
  }

  if (moving > 0) {
    sendError(F("BUSY"));
    return;
  }

  if (readLimit(swClosed)) {
    state = ST_CLOSED;
    sendOk();
    return;
  }

  startMotion(-1);
  sendOk();
}

void handleStop()
{
  /* STOP est la seule commande qui efface un defaut : c'est le geste
   * d'acquittement explicite de l'operateur. */
  fault = false;

  if (phase == PH_RAMP_DOWN) {
    sendOk();
    return;
  }

  if (phase == PH_IDLE) {
    state = ST_STOPPED;
  } else {
    stopMotion();
  }

  sendOk();
}

void handleLine(const char *line)
{
  if (strcmp(line, "PING") == 0 || strcmp(line, "STATUS") == 0) {
    sendOk();
    return;
  }

  if (strcmp(line, "OPEN") == 0) {
    handleOpen();
    return;
  }

  if (strcmp(line, "CLOSE") == 0) {
    handleClose();
    return;
  }

  if (strcmp(line, "STOP") == 0) {
    handleStop();
    return;
  }

  sendError(F("UNKNOWN_CMD"));
}

/* Lecteur non bloquant : on vide ce qui est disponible, sans jamais
 * attendre. Un caractere a la fois, borne par ROOF_LINE_MAX. */
void pollSerial()
{
  while (Serial.available() > 0) {
    int c = Serial.read();

    if (c < 0) {
      return;
    }

    if (c == '\r' || c == '\n') {
      if (lineOverflow) {
        lineOverflow = false;
        lineLen = 0;
        sendError(F("LINE_TOO_LONG"));
      } else if (lineLen > 0) {
        lineBuf[lineLen] = '\0';
        lineLen = 0;
        handleLine(lineBuf);
      }
      continue;
    }

    if (c >= 'a' && c <= 'z') {
      c -= 32;  /* majuscules : la comparaison est insensible a la casse */
    }

    if (lineLen < ROOF_LINE_MAX) {
      lineBuf[lineLen++] = (char)c;
    } else {
      lineOverflow = true;
    }
  }
}

/* -- Securite ------------------------------------------------------------ */

/* Verifie les butees et les temporisations pendant le mouvement.
 * Appelee a chaque iteration, avant la mise a jour du moteur. */
void checkSafety()
{
  if (phase != PH_RAMP_UP && phase != PH_RUN) {
    return;
  }

  uint32_t now = millis();
  uint32_t elapsed = now - motionStart;

  bool atOpen = readLimit(swOpen);
  bool atClosed = readLimit(swClosed);

  if (direction > 0) {
    if (atOpen) {
      finishMotion(ST_OPENED);
      return;
    }
    /* La butee de depart devrait etre relachee : sinon le toit est bloque. */
    if (atClosed && elapsed > ROOF_NO_MOTION_MS) {
      raiseFault(F("NO_MOTION"));
      return;
    }
  } else if (direction < 0) {
    if (atClosed) {
      finishMotion(ST_CLOSED);
      return;
    }
    if (atOpen && elapsed > ROOF_NO_MOTION_MS) {
      raiseFault(F("NO_MOTION"));
      return;
    }
  }

  if (elapsed > ROOF_MAX_TRAVEL_MS) {
    raiseFault(F("TIMEOUT"));
  }
}

/* Moteur a l'arret : on recale l'etat sur les butees.
 * Couvre l'arrivee sur une butee pendant une deceleration, et un deplacement
 * a la main toit hors tension. */
void refreshIdleState()
{
  if (phase != PH_IDLE || fault) {
    return;
  }

  bool atOpen = readLimit(swOpen);
  bool atClosed = readLimit(swClosed);

  if (atOpen && atClosed) {
    /* Impossible mecaniquement : fils en court-circuit ou butees
     * inversees. On ne bougera plus tant que STOP n'a pas acquitte. */
    raiseFault(F("LIMITS"));
    return;
  }

  if (atOpen && state != ST_OPENED) {
    state = ST_OPENED;
    sendEvent(F("OPENED"));
  } else if (atClosed && state != ST_CLOSED) {
    state = ST_CLOSED;
    sendEvent(F("CLOSED"));
  }
}

/* -- Moteur : rampes et phases ------------------------------------------- */

void updateMotor()
{
  uint32_t now = millis();

  switch (phase) {
    case PH_IDLE:
      return;

    case PH_WAIT:
      if ((now - phaseStart) < ROOF_DIRECTION_DEAD_MS) {
        return;
      }
      enableMotor();
      phase = PH_RAMP_UP;
      phaseStart = now;
      motionStart = now;
      pwm = ROOF_PWM_MIN;
      writePwm();
      return;

    case PH_RAMP_UP: {
      uint32_t elapsed = now - phaseStart;
      pwm = rampValue(elapsed, ROOF_RAMP_START_MS, ROOF_PWM_MIN, ROOF_PWM_MAX);
      writePwm();
      if (elapsed >= ROOF_RAMP_START_MS) {
        phase = PH_RUN;
      }
      return;
    }

    case PH_RUN:
      pwm = ROOF_PWM_MAX;
      writePwm();
      return;

    case PH_RAMP_DOWN: {
      uint32_t elapsed = now - phaseStart;
      pwm = rampValue(elapsed, ROOF_RAMP_STOP_MS, rampFrom, 0);
      writePwm();
      if (elapsed >= ROOF_RAMP_STOP_MS) {
        cutMotor();
      }
      return;
    }
  }
}

/* -- Cycle de vie -------------------------------------------------------- */

void setup()
{
  pinMode(PIN_LIMIT_OPEN, INPUT_PULLUP);
  pinMode(PIN_LIMIT_CLOSED, INPUT_PULLUP);

  pinMode(PIN_BTS_RPWM, OUTPUT);
  pinMode(PIN_BTS_LPWM, OUTPUT);
  pinMode(PIN_BTS_REN, OUTPUT);
  pinMode(PIN_BTS_LEN, OUTPUT);

  /* Moteur coupe avant toute autre chose. */
  cutMotor();

  Serial.begin(ROOF_BAUDRATE);

  initLimit(swOpen);
  initLimit(swClosed);

  if (swOpen.stable && swClosed.stable) {
    fault = true;
    state = ST_ERROR;
    sendEvent(F("LIMITS"));
    return;
  }

  if (swOpen.stable) {
    state = ST_OPENED;
  } else if (swClosed.stable) {
    state = ST_CLOSED;
  } else {
    /* Toit entre deux butees : position inconnue. Les mouvements restent
     * permis, les butees s'en chargeront. */
    state = ST_UNKNOWN;
  }

  sendEvent(F("BOOT"));
}

void loop()
{
  /* Ordre volontaire : securite d'abord, moteur ensuite, serie en dernier.
   * Une rafale de commandes ne retarde jamais un arret sur butee. */
  checkSafety();
  updateMotor();
  refreshIdleState();
  pollSerial();
}
