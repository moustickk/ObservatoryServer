/*
 * roof_config.h - parametres de compilation du controleur de toit.
 *
 * Ce fichier est fait pour etre REGENERE par l'interface web (phase 10) :
 * chaque valeur est protegee par #ifndef, donc une valeur passee en option
 * de compilation (-DROOF_MAX_TRAVEL_MS=45000) prend le dessus sans modifier
 * le fichier.
 *
 * Les unites sont explicites dans les noms : _MS pour les millisecondes,
 * PWM pour les rapports cycliques (0-255).
 */

#ifndef ROOF_CONFIG_H
#define ROOF_CONFIG_H

/* -- Brochage -------------------------------------------------------------
 *
 * ATTENTION : les fins de course sont des contacts NORMALEMENT FERMES
 * cables entre la broche et GND, avec la resistance de tirage interne
 * (INPUT_PULLUP). Consequence :
 *
 *   contact au repos (toit ailleurs)  -> circuit ferme  -> LOW
 *   contact actionne (toit en butee)  -> circuit ouvert -> HIGH
 *   fil coupe                         -> circuit ouvert -> HIGH
 *
 * HIGH signifie donc "en butee". Un fil coupe est vu comme une butee, ce
 * qui arrete le mouvement : c'est le sens de securite recherche.
 */
#ifndef PIN_LIMIT_OPEN
#define PIN_LIMIT_OPEN        2
#endif

#ifndef PIN_LIMIT_CLOSED
#define PIN_LIMIT_CLOSED      3
#endif

/* Driver BTS7960 : RPWM/LPWM portent le sens et la vitesse,
 * R_EN/L_EN les entrees de validation des demi-ponts. */
#ifndef PIN_BTS_RPWM
#define PIN_BTS_RPWM          5
#endif

#ifndef PIN_BTS_LPWM
#define PIN_BTS_LPWM          6
#endif

#ifndef PIN_BTS_REN
#define PIN_BTS_REN           7
#endif

#ifndef PIN_BTS_LEN
#define PIN_BTS_LEN           8
#endif

/* -- Temporisations ------------------------------------------------------ */

/* Arret de securite : au-dela, le firmware coupe le moteur et passe en
 * defaut. Doit rester SUPERIEUR au temps de trajet reel et A EGAL de la
 * valeur `max_travel_time` du serveur, pour que ce soit toujours le
 * firmware qui tranche.
 *
 * Trajet mesure sur l'installation le 24/10/2026 :
 *   ouverture 47,64 s - fermeture 47,11 s (mesure depuis la commande,
 *   donc rampe et temps mort inclus).
 * Valeur retenue : 50 s, soit environ 2,4 s de marge. C'est volontairement
 * serre : un toit qui force au-dela est un toit qui coince. Si le froid ou
 * la graisse allongent le trajet, remonter cette valeur EN MEME TEMPS que
 * `max_travel_time` cote serveur, sinon le serveur croira a une panne. */
#ifndef ROOF_MAX_TRAVEL_MS
#define ROOF_MAX_TRAVEL_MS    50000UL
#endif

/* Si la butee de depart n'est pas relachee apres ce delai, le toit ne bouge
 * pas : courroie, driver ou moteur hors service. */
#ifndef ROOF_NO_MOTION_MS
#define ROOF_NO_MOTION_MS     4000UL
#endif

/* Anti-rebond des fins de course. Un toit roulant vibre : 30 ms suffisent
 * a eliminer les rebonds mecaniques sans retarder l'arret de facon sensible. */
#ifndef ROOF_DEBOUNCE_MS
#define ROOF_DEBOUNCE_MS      30UL
#endif

/* Temps mort entre l'arret du moteur et le depart dans l'autre sens.
 * Protege le driver et la mecanique d'une inversion brutale. */
#ifndef ROOF_DIRECTION_DEAD_MS
#define ROOF_DIRECTION_DEAD_MS 400UL
#endif

/* Rampe de demarrage : le couple d'arrachement est plus faible a basse
 * vitesse, on part donc d'un rapport cyclique deja consequent. */
#ifndef ROOF_RAMP_START_MS
#define ROOF_RAMP_START_MS    900UL
#endif

/* Rampe d'arret sur commande STOP (pas sur fin de course ni sur defaut,
 * qui coupent immediatement). */
#ifndef ROOF_RAMP_STOP_MS
#define ROOF_RAMP_STOP_MS     200UL
#endif

/* -- Vitesses ------------------------------------------------------------ */

/* A augmenter si le toit ne demarre pas : c'est le symptome typique d'un
 * rapport cyclique trop faible. Le defaut NO_MOTION le signalera. */
#ifndef ROOF_PWM_MIN
#define ROOF_PWM_MIN          110
#endif

#ifndef ROOF_PWM_MAX
#define ROOF_PWM_MAX          255
#endif

/* -- Liaison serie ------------------------------------------------------- */

#ifndef ROOF_BAUDRATE
#define ROOF_BAUDRATE         115200UL
#endif

/* Longueur maximale d'une commande recue, hors fin de ligne. Au-dela, la
 * ligne est rejetee : cela borne la memoire utilisee et interdit toute
 * saturation par un flux parasite. */
#ifndef ROOF_LINE_MAX
#define ROOF_LINE_MAX         32
#endif

#endif /* ROOF_CONFIG_H */
