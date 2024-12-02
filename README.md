1 2 3

## TEMA 1 - Retele locale - Stan Andrei Razvan 333CAa

# Task 1

La acest task am avut de implementat tabela de mac-uri si functionalitatea basic a switch-ului (sa trimita frame-uri de la sursa la destinatie la nivelul 2 al stivei OSI).
Pentru asta am creat `MAC_table`, care este tabela de mac-uri deja gasite de catre switch.

Functiile `is_unicast` si `is_broadcast` verifica daca pachetul primit este un pachet de broadcast (pentru gasirea mac-ului destinatarului) sau este un pachet adresat specific unui host. Acestea sunt simple comparatii cu adresa de broadcast. (FF:FF:FF:FF:FF:FF)

Dupa ce am facut aceste lucruri, m-am asigurat ca fiecare mac primit de switch va fi salvat in tabela acestuia de mac-uri.
```
    if src_mac not in MAC_table:
        MAC_table[src_mac] = interface
```
Apoi tot ce am facut a fost sa implementez in Python pseudocod-ul primit in enunt. Practic, daca nu avem adresa mac salvata deja, va trebui sa facem broadcast sa o gasim.
Sau, daca frame-ul primit este unul de broadcast, atunci trebuie sa il trimitem mai departe. Functia `broadcast` este cea care se ocupa de broadcast.

# Task 2

Pentru acest task a fost nevoie sa citesc din fisierele de configurare din schelet. Am scris functia `read_config` in acest scop.
Functia retuneaza priority value-ul pe care il voi folosi la task-ul 3. Functia `read_config` primeste ca parametru id-ul switch-ului pentru a sti din ce fisier sa citeasca.
Daca linia se trmina in T, stim ca este un port trunk. In `VLAN_table` valoarea pe care o pun pentru un port trunk este -1.
Daca nu e port trunk atunci valoarea va fi tag-ul de vlan.

Dupa asta a trbuit sa modific implementarea de la task-ul 1. Prima data verific daca frame-ul primit este tagged sau untagged.
Daca este tagged, ii scot tag-ul.
In implementarea de forwarding am adaugat inca un if, unde verific daca se trimite un frame in acelasi vlan sau prin port trunk.
```
    if VLAN_table[MAC_table[dest_mac]] == vlan:
```
Aici vlan este valoarea tag-ului primit sau -1 daca avem un port trunk.

Acest if functioneaza pentru toate cazurile pentru ca daca avem un port trunk, valoare in VLAN_table pentru acea interfata fi -1, adica aceeasi valoare ca variabila vlan.
Idem pentru cazul in care avem un vlan tag.

# Task 3

(bid == bridge id)

Pentru a implementa acest task am incercat sa traduc pseudocod-ul si sa inteleg ce se intampla in el.

Am creat si aici o tabela de stari `STATE_table`. Valoarea 0 este starea `BLOCKING` si valoarea 1 inseamna `LISTENING` / `DESIGNATED`, intrucat nu am avut nevoie de ambele.

In functia `init_bpdu` fac toate setarile initiale (ex: completez tabela de stari, setez `own_bridge_id` sa aibe valoarea de prioritate din `read_config` etc.).
La final dau return la toate variabilele necesare.

O alta functie pe care am scris-o pentru acest task este `send_bpdu` unde formez un frame BPDU adunand in data toate campurile din enunt, chiar si cele pe care nu le modificam pentru a imi fi mai usor in implementare.

Apoi am completat functia `send_bpdu_every_sec`. Aici verific daca switch-ul este root, daca intr-adevar este acesta va trimite un frame BPDU pe toate porturile trunk. 

Marea majoritate a codului scris este in main, unde, dupa ce verific daca am primit un frame BPDU (folosind adresa de multicast), fac toate verificarile din algoritmul dar in enunt. 

Prima data m-am asigurat (prin variabile `am_i_root`) ca daca own_bid == root_bid, atunci noi suntem sigur switch-ul root, pentru a nu face mereu aceasta verificare.

Daca am primit pachet de la un switch cu bid-ul mai mic decat cel pe care il consideram noi root, atunci acel bid devine root_bid si crestem cost-ul si actualizam root port-ul. 
Apoi setam pe BLOCKING (valoarea 0) toate porturile trunk care nu sunt root si trimitem pe acestea un frame BPDU cu `send_bpdu`.

Urmatorul pas este sa verificam daca am primit frame de la root bridge. Daca primim frame de la root bridge prin root port atunci doar actualizam costul pana la root bridge. 
Daca nu primim frame-ul prin root port inseamna ca acesta este un port designated si trebuie sa ne asiguram ca este in starea corecta, adica are valoarea 1 in tabela de stari. 

Daca sender_bid este acelasi cu bid-ul nostru rezulta ca avem un loop care trebuie rezolva. Acesta se rezolva prin a pune interfata pe starea de `BLOCKING`.

Singurul lucru care se mia intampla aici este verificarea pentru a ne da seama daca switch-ul curent este root. Daca este root ii punem toate interfetele pe starea `LISTENING`.

O alta modificare care a trebuit facuta pentru ca implementarea de BPDU sa functioneze cum trebuie este in functia `broadcast`. Aici a trebuit sa mai adaug o conditie la if-ul care se asigura ca frame-ul sa nu fie trimis si pe interfata pe care a venit.
Conditia este ca interfata sa fie pe starea `LISTENING` (1 in tabela de stari). Daca nu faceam aceasta modificare atunci am fi avut loop-uri.
















