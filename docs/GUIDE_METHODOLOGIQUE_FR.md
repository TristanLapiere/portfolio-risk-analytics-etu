# Guide méthodologique — Portfolio Risk Analytics

## 1. À quoi sert l’application ?

Cette application transforme un historique de prix en un diagnostic quantitatif
d’un portefeuille multi-actifs. Elle répond à quatre questions pratiques :

1. **Quelle est la valeur du portefeuille et comment a-t-elle évolué ?**
2. **Quelle amplitude de variation le portefeuille a-t-il connue ?**
3. **À quelles pertes historiques ou théoriques faut-il s’attendre dans la
   queue défavorable de la distribution ?**
4. **Quels actifs portent le risque, et lesquels le diversifient ou le couvrent ?**

Les résultats sont des estimations calculées à partir des données importées.
Ils servent à explorer et comparer des profils de risque ; ils ne prédisent pas
les rendements futurs et ne constituent pas une recommandation d’investissement.

## 2. Données nécessaires

Importer un seul fichier CSV au format « long » : une ligne par actif et par date.

```csv
date,symbol,close,quantity
2025-01-02,ALFA,100,10
2025-01-02,BETA,250,4
2025-01-03,ALFA,103,10
2025-01-03,BETA,248,4
```

| Colonne | Rôle |
| --- | --- |
| `date` | Date de clôture au format `AAAA-MM-JJ` |
| `symbol` | Code de l’actif |
| `close` | Cours de clôture brut positif de l’actif à cette date |
| `adjusted_close` | Facultatif : cours ajusté des distributions et opérations sur titres |
| `quantity` | Quantité détenue ; elle doit rester constante pour un actif donné |

Le fichier doit contenir au moins **trois dates distinctes**, chaque date doit
comporter un cours pour chaque actif, et il ne doit pas y avoir de doublons
actif-date. Les lignes peuvent être fournies dans n’importe quel ordre : les
dates sont triées au chargement. Les CSV avec virgule décimale et séparateur
point-virgule sont acceptés.

Les exemples `ALFA` et `BETA` sont fictifs. Pour analyser plusieurs portefeuilles
ou plusieurs scénarios, préparer un fichier par configuration de quantités.

## 3. Notations utilisées

- \(i\) désigne un actif ; \(t\) une date d’observation.
- \(P_{i,t}\) est le cours de clôture de l’actif \(i\) à la date \(t\).
- \(P^{\mathrm{adj}}_{i,t}\) est le cours ajusté des distributions, s’il est fourni.
- \(q_i\) est sa quantité, supposée constante dans le temps.
- \(V_t = \sum_i q_i P_{i,t}\) est la valeur du portefeuille à la date \(t\).
- \(N\) est le nombre de variations entre les observations, donc le nombre de
  dates moins un.
- \(r_{p,t}\) est le rendement simple du portefeuille entre deux observations.
- \(r_{f,a}\) est le taux sans risque annuel choisi dans le panneau latéral.
- \(T=252\) est le nombre conventionnel de séances de marché par an.

Sauf indication contraire, les mesures de risque affichées comme pourcentages
sont des rendements ou pertes **sur une observation**, tandis que les
volatilités et ratios annualisés utilisent la convention de 252 séances.

## 4. Valeur, performance et allocation

### Valeur d’une position

Pour chaque actif :

\[
\text{Valeur}_{i,t} = q_i P_{i,t}
\]

La valeur de marché totale à la dernière date est :

\[
V_{\text{dernier}} = \sum_i q_i P_{i,\text{dernier}}
\]

La valeur initiale est calculée de la même manière à la première date.
Le tableau des positions affiche également le résultat non réalisé depuis cette
première observation :

\[
\text{P\&L}_i =
q_i(P_{i,\text{dernier}} - P_{i,\text{premier}})
\]

\[
\text{Rendement}_i =
\frac{P_{i,\text{dernier}}-P_{i,\text{premier}}}
     {P_{i,\text{premier}}}
\]

Le rendement cumulé **des cours bruts** (celui utilisé par le tableau des
positions) est :

\[
R_{\text{prix}} = \frac{V_{\text{dernier}}}{V_{\text{premier}}}-1
\]

Le poids de marché d’un actif à la dernière date est :

\[
w_i = \frac{q_iP_{i,\text{dernier}}}{V_{\text{dernier}}}
\]

**Interprétation :** ces indicateurs décrivent l’évolution de la valeur des
positions entre le premier et le dernier cours fourni. La quantité est figée :
il ne s’agit pas d’un historique de transactions ou d’un rendement tenant compte
des apports et retraits.

## 5. Rendements et risque global

### Rendements simples

Sans colonne `adjusted_close`, le rendement historique de l’actif utilise les
cours bruts :

\[
r_{i,t} = \frac{P_{i,t}}{P_{i,t-1}}-1
\]

Pour unifier les deux cas, on définit \(P^*_{i,t}\) comme le cours brut si
`adjusted_close` est absent, et comme le cours ajusté si cette colonne est
fournie :

\[
P^*_{i,t} =
\begin{cases}
P_{i,t}, & \text{sans cours ajusté}\\
P^{\mathrm{adj}}_{i,t}, & \text{avec cours ajusté}
\end{cases}
\]

La valeur synthétique à quantité fixe est alors :

\[
V^*_t = \sum_i q_iP^*_{i,t},
\qquad
r_{p,t} = \frac{V^*_t}{V^*_{t-1}}-1
\]

Pour afficher cet indice à l’échelle de la valeur de marché brute initiale, il
est remis à l’échelle une seule fois au début :

\[
V^{\mathrm{TR}}_t =
\frac{V_0}{V^*_0}V^*_t
\]

Les rendements ajustés approchent un rendement total avec distributions
réinvesties pour les quantités détenues ; aucun rééquilibrage quotidien n’est
appliqué. Les cours bruts restent utilisés pour valoriser les positions et
initialiser le spot de l’onglet Options ; le P&L des positions ne comprend donc
pas les distributions. Sans cours ajustés, les rendements sont des rendements de
prix seulement. Ainsi, le rendement de période dans **Performance** et les
métriques de risque peuvent différer du P&L / rendement affiché pour les positions.

### Volatilité historique annualisée

L’application calcule l’écart-type **échantillonnal** des rendements du
portefeuille :

\[
s_p = \sqrt{\frac{1}{N-1}\sum_{t=1}^{N}(r_{p,t}-\bar r_p)^2}
\]

Puis l’annualise :

\[
\sigma_{\text{annuelle}} = s_p\sqrt{252}
\]

**À quoi ça sert ?** La volatilité résume la dispersion des rendements passés.
Une valeur élevée indique des variations historiques plus amples ; elle ne dit
pas à elle seule si la performance moyenne est bonne ou mauvaise et ne mesure
pas une perte maximale.

### Volatilité EWMA

La volatilité EWMA accorde davantage de poids aux mouvements récents. La
variance journalière est initialisée au carré du premier rendement puis mise à
jour récursivement :

\[
h_1 = r_{p,1}^2
\]

\[
h_t = 0{,}94h_{t-1}+0{,}06r_{p,t}^2
\]

\[
\sigma_{\text{EWMA, annuelle}} = \sqrt{252h_N}
\]

Le paramètre \(\lambda=0{,}94\) implique un poids décroissant exponentiellement
avec l’ancienneté. **À quoi ça sert ?** Comparer une estimation sensible aux
variations récentes à la volatilité historique non pondérée. Sur une série
courte, le résultat dépend fortement des premiers rendements et reste fragile.

### Ratio de Sharpe

Le ratio affiché est :

\[
\text{Sharpe} =
\frac{252\bar r_p-r_{f,a}}{\sigma_{\text{annuelle}}}
\]

Le rendement moyen quotidien est annualisé par multiplication par 252 ; le
taux sans risque est soustrait au numérateur. **À quoi ça sert ?** Résumer la
performance excédentaire par unité de volatilité totale. Un ratio plus élevé
signifie davantage de rendement excédentaire par unité de risque mesuré, mais
seulement sur l’échantillon et selon ces conventions. Le ratio n’est pas défini
si la volatilité est nulle.

### Ratio de Sortino

La déviation baissière quotidienne utilisée est la racine de la moyenne des
carrés des rendements négatifs, les rendements positifs étant ramenés à zéro :

\[
d_p = \sqrt{\frac{1}{N}\sum_{t=1}^{N}\min(r_{p,t},0)^2}
\]

\[
\text{Sortino} =
\frac{252\bar r_p-r_{f,a}}{d_p\sqrt{252}}
\]

**À quoi ça sert ?** Comme le Sharpe, il met le rendement excédentaire en regard
du risque, mais pénalise seulement les observations sous zéro. Il n’est pas
défini si aucun rendement négatif ne produit une déviation baissière positive.

## 6. Pertes extrêmes : VaR et Expected Shortfall

Les deux mesures sont calculées pour un horizon d’une observation (généralement
une séance si les dates du CSV correspondent à des séances de marché). Le niveau
de confiance est réglable dans l’interface : 90 %, 95 % ou 99 %. Dans les
formules ci-dessous, \(\alpha\) désigne ce niveau et \(1-\alpha\) la probabilité
de queue.

### VaR historique

L’application trie les rendements observés et estime le quantile à 5 % par
interpolation linéaire entre les deux observations adjacentes :

\[
q_{1-\alpha} = \text{quantile}_{1-\alpha}(r_{p,1},\ldots,r_{p,N})
\]

\[
\text{VaR}_{\alpha,\text{historique}} = \max(0,-q_{1-\alpha})
\]

**Interprétation :** quand cette VaR est positive, le quantile de perte
historique à 95 % est approximativement cette fraction du portefeuille sur un
jour. Ce n’est **pas** une perte maximale : environ 5 % des rendements peuvent
être pires dans le modèle empirique, et rien ne borne leur ampleur.

### Expected Shortfall historique

Le code prend les rendements observés inférieurs ou égaux au quantile précédent
et calcule l’opposé de leur moyenne :

\[
\text{ES}_{\alpha,\text{historique}} =
\max\left(0,-\operatorname{moyenne}
  \{r_{p,t}: r_{p,t}\leq q_{1-\alpha}\}\right)
\]

**À quoi ça sert ?** Compléter la VaR en estimant la perte moyenne dans la
queue défavorable retenue. Cette estimation empirique dépend du petit nombre
d’observations extrêmes présentes dans l’historique.

### VaR et Expected Shortfall paramétriques gaussiens

La variante paramétrique suppose que les rendements suivent une loi normale
\(\mathcal N(\bar r_p,s_p^2)\). La fonction de répartition de la loi normale
standard est notée \(\Phi\), sa densité \(\phi\), et
\(z_\alpha=\Phi^{-1}(\alpha)\). À 95 %, \(z_\alpha\approx1{,}64485\) et
\(\phi(z_\alpha)/(1-\alpha)\approx2{,}06271\) :

\[
\text{VaR}_{\alpha,\text{normale}} =
\max(0,-(\bar r_p-z_\alpha s_p))
\]

\[
\text{ES}_{\alpha,\text{normale}} =
\max(0,-\bar r_p+
  \frac{\phi(z_\alpha)}{1-\alpha}s_p)
\]

**À quoi ça sert ?** Comparer l’estimation empirique à une estimation
paramétrique compacte. Les résultats peuvent différer, surtout en présence de
queues épaisses, d’asymétrie ou d’une série très courte. L’hypothèse normale
peut sous-estimer le risque de pertes extrêmes observées en marché.

Pour convertir approximativement une perte en montant, multiplier le pourcentage
de VaR/ES par la valeur de portefeuille considérée. Par exemple, une VaR
journalière de 1 % sur un portefeuille de 10 000 € représente environ 100 €.
Ce montant reste une estimation, et non une garantie de perte maximale.

## 7. Drawdown et ratio de Calmar

À chaque date, le sommet historique courant de l’indice de performance utilisé
par l’analyse de risque est :

\[
H_t = \max_{s\leq t} V^{\mathrm{TR}}_s
\]

Le drawdown à la date \(t\) est :

\[
D_t = \frac{V^{\mathrm{TR}}_t}{H_t}-1
\]

Le drawdown maximal affiché est le minimum de la série \(D_t\). Il est nul ou
négatif ; par exemple, \(-20\%\) signifie que la valeur est descendue jusqu’à
20 % sous un sommet précédent dans l’historique observé.

Le rendement annualisé géométrique utilisé pour le Calmar est :

\[
R_{\text{annuel géométrique}} =
\left(\frac{V^{\mathrm{TR}}_N}{V^{\mathrm{TR}}_0}\right)^{252/N}-1
\]

\[
\text{Calmar} =
\frac{R_{\text{annuel géométrique}}}
     {|D_{\max}|}
\]

Le ratio de Calmar compare le rendement annualisé composé au drawdown maximal.
Il n’est pas calculé lorsque le drawdown maximal est nul. Il peut être très
grand lorsque l’historique est court et le drawdown observé minime : ce n’est
pas une promesse de rendement futur.

## 8. Corrélations et covariance

La covariance échantillonnale entre les rendements de deux actifs est :

\[
\operatorname{Cov}(i,j) =
\frac{1}{N-1}\sum_{t=1}^{N}
(r_{i,t}-\bar r_i)(r_{j,t}-\bar r_j)
\]

La corrélation correspondante est :

\[
\rho_{i,j} =
\frac{\operatorname{Cov}(i,j)}{\sigma_i\sigma_j}
\]

Elle varie de \(-1\) à \(+1\) :

- \(+1\) : mouvements parfaitement alignés dans l’échantillon ;
- autour de \(0\) : absence de relation linéaire marquée dans l’échantillon ;
- \(-1\) : mouvements parfaitement opposés dans l’échantillon.

Une corrélation n’implique pas une causalité. Lorsque la variance historique
d’un actif est nulle, sa corrélation n’est pas définie et la cellule est
affichée comme non disponible.

## 9. Volatilité et contribution au risque d’Euler

Pour cette décomposition, l’application construit une matrice de covariance
annualisée :

\[
\Sigma_{\text{annuelle}} = 252\Sigma_{\text{quotidienne}}
\]

Les poids \(w_i\) sont les poids de marché observés à la **dernière date** du
fichier. La volatilité modélisée du portefeuille et sa variance sont :

\[
\sigma_p = \sqrt{w^\top\Sigma_{\text{annuelle}}w}
\qquad
\sigma_p^2 = w^\top\Sigma_{\text{annuelle}}w
\]

La volatilité annualisée propre à l’actif \(i\) affichée dans le tableau est :

\[
\sigma_i = \sqrt{\Sigma_{\text{annuelle},ii}}
\]

La contribution relative d’Euler affichée pour l’actif \(i\) est :

\[
\text{Contribution}_i =
\frac{w_i(\Sigma_{\text{annuelle}}w)_i}{\sigma_p^2}
=
\frac{w_i\sum_j\Sigma_{\text{annuelle},ij}w_j}{\sigma_p^2}
\]

Quand \(\sigma_p>0\), les contributions s’additionnent à 1 (100 %), à l’erreur
d’arrondi près.

**Exemple d’interprétation :** une contribution de 70 % signifie que l’actif
représente 70 % de la variance du portefeuille dans cette décomposition au
dernier poids et selon les covariances estimées. Une contribution négative
signifie qu’au vu des covariances et des poids actuels, l’actif réduit la
variance du portefeuille : il joue un rôle de diversification ou de couverture.
Un actif peut donc contribuer à plus de 100 % si un autre apporte une
contribution négative. Ce pourcentage n’est pas la part de valeur investie.

**Point méthodologique important :** l’historique de valeur et les rendements
du portefeuille utilisent les quantités fixes à chaque date. La décomposition
d’Euler, elle, combine la covariance historique avec les poids de marché de la
dernière date. C’est une attribution de risque « instantanée » au portefeuille
actuel ; elle n’est pas identique à une décomposition de chaque rendement
historique si les poids ont évolué.

## 10. Volatilité glissante affichée dans l’onglet Overview

Le graphique calcule le rendement quotidien du portefeuille puis l’écart-type
échantillonnal sur une fenêtre mobile de 21 rendements :

\[
\sigma_{21,t} =
\operatorname{écart-type}(r_{p,t-20},\ldots,r_{p,t})\sqrt{252}
\]

Il faut donc au moins 22 valeurs de portefeuille, soit 22 dates, pour obtenir
une première fenêtre complète. Ce graphique aide à voir si la volatilité
récente augmente ou diminue ; il n’est pas affiché quand l’historique est trop
court.

## 11. Exemple d’utilisation, de l’import à l’interprétation

1. Préparer les cours de clôture et les quantités dans le format ci-dessus.
2. Ouvrir le dashboard, importer le CSV et corriger les erreurs de format
   signalées s’il y en a.
3. Examiner l’évolution de la valeur et des actifs rebasés à 100 dans
   **Overview**.
4. Examiner dans **Risk** la volatilité, les ratios, les deux familles de VaR/ES,
   le drawdown et les contributions d’Euler.
5. Examiner dans **Holdings** les quantités, cours initial et final, P&L et
   poids actuels.
6. Modifier le taux sans risque dans le panneau latéral pour observer son effet
   sur les ratios de Sharpe et Sortino. Il ne modifie pas les autres indicateurs.

Le taux sans risque saisi est annuel et compris entre 0 % et 20 % dans le
dashboard. Le programme en ligne de commande accepte un taux sous forme
décimale, par exemple `0.03` pour 3 %.

### Scénarios de stress

L’onglet **Stress tests** propose des chocs parallèles de \(-30\%\) à \(+10\%\)
appliqués à tous les cours actuels, ainsi qu’un scénario personnalisé où l’on
choisit un choc par actif entre \(-100\%\) et \(+100\%\). Pour le choc \(s_i\)
de l’actif \(i\), l’impact instantané est :

\[
\Delta V = \sum_i q_iP_{i,\text{dernier}}s_i
\]

\[
V_{\text{stress}}=V_{\text{actuel}}+\Delta V
\]

Ces scénarios supposent un choc immédiat proportionnel aux valeurs de marché
actuelles. Ils ne modélisent ni la réaction des corrélations, ni les prix de
liquidation, ni les effets de second ordre, ni la probabilité du scénario. Ils
servent à répondre à une question « que se passerait-il si ? », pas à prévoir
ce qui va arriver.

### Devise et exports

Le sélecteur de devise change uniquement le **libellé** monétaire. Il ne convertit
pas les prix : sélectionner USD pour des prix en EUR ne transforme pas ces montants
en dollars. Les trois exports CSV permettent de récupérer positions, historique
de performance rebasé et indicateurs de risque, avec le niveau de confiance
retenu pour l’analyse.

### Import de cours depuis Yahoo Finance

Le choix **Fetch from Yahoo Finance** télécharge, à la demande et sans clé API,
les cours journaliers `close` et `adjclose` pour les tickers et dates saisis.
Seules les observations communes aux tickers sont conservées ; chaque ticker
reçoit la quantité indiquée dans le formulaire. Le CSV téléchargé peut ensuite
être réutilisé.

Cette intégration utilise un endpoint public non officiel : il peut être limité,
modifié ou indisponible. Les données ne sont pas garanties en temps réel et ne
constituent pas un flux de trading. Respecter les conditions d’utilisation du
fournisseur, surtout avant redistribution. La colonne ajustée sert aux
rendements historiques ; ce n’est pas un cours auquel exécuter une transaction.

## 12. Simulation d’options européennes

L’onglet **Options** valorise un call ou un put européen à partir du spot \(S\)
(par défaut le dernier cours brut de l’actif choisi), du strike \(K\), du temps
calendaire jusqu’à l’échéance \(T\) exprimé en années, de la volatilité annualisée
\(\sigma\), du taux sans risque continu \(r\) et du rendement continu des
distributions \(q\). La volatilité initiale proposée est la volatilité
historique de l’actif, si calculable ; elle n’est pas une volatilité implicite.
L’utilisateur peut modifier toutes ces hypothèses.

\[
d_1 =
\frac{\ln(S/K)+(r-q+\sigma^2/2)T}{\sigma\sqrt{T}},
\qquad
d_2 = d_1-\sigma\sqrt{T}
\]

En notant \(\Phi\) la fonction de répartition normale standard :

\[
C = Se^{-qT}\Phi(d_1)-Ke^{-rT}\Phi(d_2)
\]

\[
P = Ke^{-rT}\Phi(-d_2)-Se^{-qT}\Phi(-d_1)
\]

Les sensibilités par unité sous-jacente sont :

\[
\Delta_C=e^{-qT}\Phi(d_1),\qquad
\Delta_P=e^{-qT}(\Phi(d_1)-1)
\]

\[
\Gamma = \frac{e^{-qT}\phi(d_1)}{S\sigma\sqrt{T}},
\qquad
\text{Vega}=Se^{-qT}\phi(d_1)\sqrt{T}
\]

\[
\Theta_C =
-\frac{Se^{-qT}\phi(d_1)\sigma}{2\sqrt{T}}
-rKe^{-rT}\Phi(d_2)+qSe^{-qT}\Phi(d_1)
\]

\[
\Theta_P =
-\frac{Se^{-qT}\phi(d_1)\sigma}{2\sqrt{T}}
+rKe^{-rT}\Phi(-d_2)-qSe^{-qT}\Phi(-d_1)
\]

\[
\rho_C=KTe^{-rT}\Phi(d_2),\qquad
\rho_P=-KTe^{-rT}\Phi(-d_2)
\]

Dans l’interface, Vega et Rho sont exprimés par variation d’un point de
pourcentage, Theta par jour calendaire, et les sensibilités incluent le sens de
la position, le nombre de contrats et le multiplicateur. Le tableau spot /
volatilité revalorise théoriquement l’option sous plusieurs chocs ; le graphique
temporel montre la décroissance du prix modélisé ; le graphique à l’échéance
montre le payoff moins la prime théorique actuelle.

Ce n’est pas un flux de chaîne d’options : la prime Black–Scholes est une
estimation de modèle, pas un cours acheteur/vendeur. Le modèle suppose un
exercice européen, volatilité et taux constants, rendement continu des
distributions, négociation continue et absence de frais. Il ne modélise ni
l’exercice anticipé des options américaines, ni les changements de volatilité
implicite, ni les spreads, ni les dividendes discrets.

## 13. Limites et précautions d’interprétation

- **Historique court :** trois dates suffisent techniquement à construire la
  covariance, mais pas à produire des estimations robustes. L’application
  affiche un avertissement sous 60 dates ; même 60 observations ne garantissent
  pas la représentativité d’un régime de marché.
- **Dates irrégulières :** le programme traite chaque ligne de rendement comme
  une période et annualise avec 252, sans calculer le nombre réel de jours
  ouvrés entre deux dates. Fournir de préférence des observations quotidiennes
  régulières de clôture.
- **Positions fixes :** pas de rééquilibrage, achats/ventes intermédiaires,
  commissions, spread, financement, coupons, fiscalité ni flux externes. Les
  rendements de prix seuls excluent les dividendes ; les rendements ajustés les
  approchent par réinvestissement, sans simuler de flux de trésorerie réels.
- **Données API :** l’endpoint Yahoo utilisé est non officiel ; l’historique,
  l’ajustement et la disponibilité peuvent changer. Les cours ne sont pas
  garantis en temps réel.
- **Options :** les prix sont des résultats Black–Scholes théoriques, avec des
  hypothèses simplificatrices ; ils ne remplacent ni une chaîne d’options de
  marché ni une analyse de convenance financière.
- **Quantités positives uniquement :** le format et les validations ne
  modélisent pas les positions courtes.
- **Devise :** les cours doivent être exprimés dans une devise cohérente ; le
  programme ne convertit pas les devises.
- **VaR historique :** repose directement sur les événements de l’échantillon
  et peut manquer les crises absentes des données.
- **VaR/ES gaussiens :** reposent sur l’hypothèse de normalité, qui ne décrit
  pas nécessairement les queues de distribution des marchés.
- **Annualisation :** \(\sqrt{252}\) pour la volatilité et \(252\) pour la
  moyenne arithmétique sont des conventions usuelles, pas une correction de la
  fréquence ou de la qualité des données.
- **Ratios annualisés sur peu d’observations :** un rendement annualisé ou un
  faible drawdown peut rendre le Calmar ou d’autres ratios très élevés. Ils
  doivent toujours être lus avec la longueur et la période de l’historique.
- **Corrélations instables :** elles ne sont ni constantes dans le temps ni
  prédictives ; les résultats dépendent de la période choisie.

En pratique, privilégier un historique long, cohérent et ajusté des opérations
sur titres si l’on veut interpréter des rendements. Les données de démonstration
livrées avec le projet sont fictives et trop courtes pour des conclusions
financières sérieuses.
