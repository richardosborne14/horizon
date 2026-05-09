# Communauté Coiffure — Services Catalog

**Version:** 0.1
**Date:** April 12, 2026
**Purpose:** Reference document for (1) the CoCo AI agent to recommend the correct service to users, and (2) content source for the landing page rewrite.

---

## How to Use This Document

**For the CoCo agent:** Each service section includes `[AGENT CONTEXT]` blocks with trigger phrases, qualifying questions, and the recommended action (redirect, booking, external link, etc.).

**For the landing page:** Each service section includes `[LANDING PAGE COPY]` blocks with the best existing copy to preserve/adapt, key selling points, and pricing to display.

---

## Service Categories

Communauté Coiffure's offerings fall into three categories:

1. **In-app tools** — Built into the ComCoi platform, used directly by the subscriber (Rentabilité app, pricing calculator, blog)
2. **Managed services** — Delivered by ComCoi or white-label partners, ordered through the platform (comptabilité en ligne, bulletins de salaire, création d'entreprise)
3. **Partner referrals** — External partners offering preferential rates to ComCoi members (assurance, énergie, mutuelle, coaching, formations, site web, NFC plaques)

---

## 1. Rentabilité & Calcul des Tarifs (In-App Tool)

**What it is:** The core ComCoi application. A profitability analysis and service pricing calculator that lets salon owners understand their real monthly/annual income and set prices based on their actual cost-per-minute.

**Delivery:** Self-service in-app tool, accessible after account creation.

**Pricing:** 32€ HT/mois — CCPilot (with 14-day free trial, no commitment).
Bundled with Noly accounting: PACK BIC+CCPilot 89€ HT/mois (IR), PACK BIC++CCPilot 119€ HT/mois (IS).

**Key value propositions:**
- Know exactly how much your business earns you each month after all expenses
- Calculate the real cost per minute of your time
- Set prices that cover your costs and generate profit
- Simulate scenarios (price increases, expense changes)
- Stop running your business blind

**What's included:**
- Monthly and annual profitability reporting (the "Copilot" grid)
- Setup wizard for business type and recurring expenses
- Cost-per-minute calculation engine
- Service pricing calculator (forfaits with 10-min addon, services à la carte)
- Revenue vs break-even analysis

**New features (v2):**
- 4 additional calculators: primes (employee commission), seuil de rentabilité salaire (employee break-even), volume clients, marge revente (resale margin)
- AI financial assistant
- Monthly health score (0-100)
- Expense benchmarking vs platform averages
- Business type comparison simulator (e.g., "what if I switched from micro-entreprise to EURL?")

```
[AGENT CONTEXT]
Trigger phrases:
- "combien je gagne", "ma rentabilité", "suis-je rentable"
- "calculer mes tarifs", "prix de mes prestations", "coût minute"
- "mes charges", "mes dépenses", "mon chiffre d'affaires"
- "augmenter mes bénéfices", "gagner plus", "optimiser"
- "point mort", "seuil de rentabilité"

Action: Direct to the Rentabilité tool in-app.
If user is not subscribed: Explain the 14-day free trial and 32€/mois pricing (CCPilot). If they also need accounting, explain the Packs.
If user mentions paying 99€/an: Their legacy rate is preserved — do NOT suggest migrating; they would pay more.
If user needs help using the tool: Walk them through setup or answer questions using their financial data.
```

```
[LANDING PAGE COPY — preserve/adapt]
Headline: "L'outil indispensable pour optimiser votre rentabilité et calculer vos tarifs"
Subhead: "La gestion c'est ce qui fait qu'à chiffre d'affaires égal, un coiffeur gagne plus d'argent qu'un autre."
Key line: "Ne pilotez plus votre entreprise sans savoir combien elle vous rapporte réellement chaque fin de mois."
CTA: "Testez 14 jours GRATUITEMENT — sans engagement, sans CB"
Price display: 32€ HT/mois (CCPilot)
Testimonial themes: Users discovering their real costs after years of guessing; users increasing profits by adjusting pricing; users praising Eric personally.
```

---

## 2. Comptabilité en Ligne — Noly Compta (Managed Service / White-Label Partner)

**What it is:** A white-labelled online accounting platform (powered by Noly Compta) designed for hair salons, barbers, and beauticians. Replaces traditional accountants with a digital-first approach at a fraction of the cost.

**Delivery:** Stripe subscription through ComCoi → SSO redirect to Noly Compta platform.

**Pricing (monthly, HT):**
- **PACK BIC** (sociétés commerciales à l'IR, comptabilité de trésorerie): dès 63€/mois
- **PACK BIC+** (sociétés commerciales à l'IS, comptabilité d'engagement): dès 93€/mois
- 14-day free trial, no commitment
- Bilan completion requires minimum 12 months of payments (shortfall billed as a lump sum)

**Options supplémentaires:**
- Déclaration des revenus: 10€ HT/mois
- Dépôt des comptes sociaux: 25€ HT/mois

**What's included (PACK BIC):**
- App access with dashboard
- Automatic bank data retrieval
- Automatic expense categorisation
- Expense notes / cash receipts
- Asset management (immobilisations)
- Support & advice from accounting specialists experienced in salon/beauty sector
- Annual balance sheet (bilan) preparation
- Liasse fiscale establishment
- AGA data management and transmission

**Additional in PACK BIC+:**
- TVA calculation system
- Invoice retrieval system
- Loan and deferred payment management
- Corporate tax (IS) calculation

**Key selling points:**
- Specialised in coiffure — advisors who understand salon economics
- Messaging support within 48h, plus video/phone consultations available
- User can leave their current accountant at any time (1 month notice rule); ComCoi handles the resignation letter
- Major cost savings vs traditional accountant (less than 800€/year vs thousands)

```
[AGENT CONTEXT]
Trigger phrases:
- "comptabilité", "comptable", "bilan", "liasse fiscale"
- "trop cher mon comptable", "changer de comptable"
- "TVA", "charges sociales", "déclaration"
- "Noly", "ma compta en ligne"
- "factures", "notes de frais"

Qualifying questions:
- "Quel est le statut juridique de votre entreprise ?" (determines BIC vs BIC+ pack)
- "Êtes-vous à l'IR ou à l'IS ?" (same)
- "Avez-vous déjà un comptable ?" (if yes, reassure about easy transition)

Action: Explain the two packs, help user identify which one fits, offer free trial.
If already subscribed: Redirect to Noly Compta portal.
```

```
[LANDING PAGE COPY — preserve/adapt]
Headline: "La solution de comptabilité en ligne pour une gestion financière efficace et sans tracas"
Subhead: "Avant, la compta c'était compliqué, chronovore et les honoraires coûtaient chers. Maintenant c'est facile, rapide, pas cher."
Key differentiator: "Nous sommes spécialisés en coiffure."
FAQ themes: What is accounting? Why is it expensive? How is online different? Can I leave my accountant mid-year?
Price display: "Ma compta en ligne à partir de 14€90 HT/mois" (note: this is the document management entry point, not the full accounting — see section 3 below)
```

---

## 3. Gestion des Factures / Documents Comptables (Managed Service / White-Label)

**What it is:** A document management tool that digitises the collection, organisation, and entry of accounting documents (receipts, invoices, bank reconciliation). Can be used standalone or as a complement to the full accounting packs.

**Delivery:** In-app tool (part of the Noly ecosystem).

**Pricing (monthly, HT):**
- **BASIC IR**: dès 20€/mois
- **BASIC IS**: dès 25€/mois
- 14-day free trial, no commitment

**What's included:**
- Unlimited mobile scanner
- Unlimited secure storage
- Dashboard
- Tracking reports
- Accounting entry exports (compatible with Sage, Ciel, EBP, Excel)

**Key selling points:**
- Photo a receipt → one click → it's filed and archived
- Automatic bank reconciliation (match receipts to bank transactions)
- Your accountant can log in and retrieve everything pre-sorted and numbered
- Saves time and money — can negotiate lower accountant fees since they spend less time sorting

```
[AGENT CONTEXT]
Trigger phrases:
- "factures", "documents comptables", "pièces comptables"
- "scanner", "archiver", "classer mes factures"
- "rapprochement bancaire"
- "ticket de caisse", "reçu"
- "envoyer à mon comptable"

Action: Explain the document management tool, clarify it's complementary to (not a replacement for) full accounting.
If user already has a comptable and doesn't want to switch: This tool helps them save on accountant fees by doing the sorting themselves.
```

---

## 4. Comptabilité en Retard (Managed Service)

**What it is:** A catch-up service for businesses that are behind on their accounting. ComCoi reviews the accounts and prepares the balance sheet for past fiscal years.

**Delivery:** Order through ComCoi → a collaborator contacts the user to assess the situation.

**Pricing:** dès 549€ HT/exercice

**Two formulas:**
- **BILAN EXPRESS BIC** (société commerciale à l'IR): same feature set as PACK BIC above, applied retroactively
- **BILAN EXPRESS BIC+** (société commerciale à l'IS): same feature set as PACK BIC+ above, applied retroactively

```
[AGENT CONTEXT]
Trigger phrases:
- "comptabilité en retard", "bilan en retard", "exercice en retard"
- "rattraper ma compta", "pas à jour"
- "retard comptable", "exercice précédent"

Qualifying questions:
- "De combien d'exercices êtes-vous en retard ?"
- "IR ou IS ?"

Action: Explain the service, collect basic info, and arrange for a collaborator to contact the user.
```

---

## 5. Bulletins de Salaire (Managed Service)

**What it is:** Payroll processing service. A dedicated payroll manager prepares employee pay slips and handles all social declarations.

**Delivery:** Order through ComCoi → initial dossier setup → monthly bulletin processing.

**Pricing:**
- **Dossier creation (one-time):** 65€ HT (mandatory)
- **Per bulletin:** dès 24€ HT/salarié/mois (prepaid in advance)

**Dossier creation includes:**
- URSSAF setup
- Retirement fund setup
- Provident fund (prévoyance)
- Health insurance (mutuelle)
- DGFIP
- Support through first social declaration (DSN)

**Monthly service includes:**
- Pay slip processing (creation, data entry, PDF, email delivery)
- Excel import file for payroll variables
- Pay profiles
- Employee payment journal
- SEPA transfer file export
- Accounting entry journal + export (Sage, Ciel, EBP, Excel formats)
- Social fund declarations
- Salary journal, charge reduction journal, configurable journals
- Reverse payroll (paie inversée)
- Absence and leave planning
- Monthly, partial, and event-based DSN (end of contract, sick leave, return to work) with history
- OC parameter sheet integration
- DSN return management with history
- DADSU export
- 3-year + current year data retention
- Employer attestation (Pôle Emploi)
- Work certificate
- Final settlement (solde de tout compte)
- Income tax withholding (retenue à la source)

```
[AGENT CONTEXT]
Trigger phrases:
- "bulletin de salaire", "fiche de paie", "paie"
- "salariés", "employés", "charges salariales"
- "DSN", "déclaration sociale"
- "embaucher", "embauche"

Qualifying questions:
- "Combien de salariés avez-vous ?"
- "Avez-vous déjà un gestionnaire de paie ?"

Action: Explain the service and pricing, collect number of employees, initiate dossier creation.
```

---

## 6. Création d'Entreprise (Managed Service)

**What it is:** Company formation service. ComCoi guides the user through every step of creating their business, regardless of legal structure.

**Delivery:** Online process + dedicated team support.

**Pricing:** dès 449€ HT

**Supported structures:**
- SASU
- SAS
- EURL
- SARL
- SCI
- Entreprise individuelle
- Auto-entrepreneur

**What's included:**
- Choice of legal structure (guided by ComCoi team)
- Drafting of statutes (statuts)
- Legal notices (annonces légales)
- Filing with the commercial court registry (greffe du tribunal de commerce)
- Obtaining the K-BIS

**Entry point:** Free consultation appointment to discuss the user's situation and recommend the best structure.

```
[AGENT CONTEXT]
Trigger phrases:
- "créer mon entreprise", "création de société", "ouvrir un salon"
- "statut juridique", "SASU", "EURL", "SARL", "auto-entrepreneur"
- "K-BIS", "immatriculation"
- "je veux me mettre à mon compte", "devenir indépendant"

Qualifying questions:
- "Avez-vous déjà une idée du statut juridique souhaité ?"
- "Est-ce votre premier salon ?"

Action: Book a free consultation with the ComCoi team. Provide initial guidance on structure types if the user wants preliminary info.
```

---

## 7. Approbation des Comptes / Dépôt des Comptes Sociaux (Managed Service)

**What it is:** Annual account approval and filing service. A legal obligation for companies — ComCoi handles the entire process with their legal team.

**Delivery:** Handled by ComCoi jurists, including all exchanges with the greffe.

**Pricing:** 25€ HT/mois (as an option added to accounting packs)

**What's included:**
- Account validation by expert jurists
- Filing with the commercial court registry
- All exchanges and follow-up until the filing is validated

```
[AGENT CONTEXT]
Trigger phrases:
- "approbation des comptes", "dépôt des comptes"
- "comptes annuels", "assemblée générale"
- "obligation légale", "greffe"

Action: Explain the service, offer to add it as an option to their accounting pack.
```

---

## 8. Accompagnement Entreprises en Difficulté (Managed Service)

**What it is:** Legal and strategic consultation for businesses experiencing financial difficulty — cash flow problems, inability to repay debts, questions about options.

**Delivery:** Video conference with a legal expert.

**Pricing:** 80€ HT for 1 hour of consultation

**What's included:**
- 1 hour of advice with a legal expert
- Video conference format

```
[AGENT CONTEXT]
Trigger phrases:
- "difficultés", "trésorerie", "dettes", "problèmes financiers"
- "liquidation", "redressement", "cessation"
- "je ne m'en sors pas", "je ne peux pas payer"

Action: Handle with empathy. Explain that expert legal help is available. Do NOT attempt to give legal advice. Book a consultation.
Important: This is a sensitive topic. The agent should be supportive and non-judgmental.
```

---

## 9. Assurance Professionnelle (Partner Referral)

**What it is:** A free, no-commitment insurance comparison service. Users answer a few questions and receive quotes from multiple insurers.

**Delivery:** External comparison tool → user can subscribe online or request a callback from the insurer.

**Pricing:** Free service (ComCoi earns referral commission)

**Key selling points:**
- Compare quotes in 2 minutes
- No commitment
- Can switch insurer after 1 year of contract at any time

```
[AGENT CONTEXT]
Trigger phrases:
- "assurance", "assurance professionnelle", "assurance salon"
- "contrat d'assurance", "changer d'assurance"
- "économies assurance"

Action: Redirect to the insurance comparison tool. Remind user it's free and non-binding.
```

---

## 10. Fournisseurs d'Énergie (Partner Referral)

**What it is:** Free energy provider comparison service. ComCoi analyses the user's situation and proposes the best market offers for electricity/energy.

**Delivery:** External comparison tool → subscribe online or request a callback from the provider.

**Pricing:** Free service

```
[AGENT CONTEXT]
Trigger phrases:
- "électricité", "énergie", "fournisseur d'énergie"
- "facture d'électricité", "EDF", "changer de fournisseur"
- "économies énergie"

Action: Redirect to the energy comparison tool. Remind user it's free and non-binding.
```

---

## 11. Coaching (Partner Referral)

**What it is:** Professional coaching for salon owners and managers, focused on overcoming obstacles and reaching business goals. Pragmatic, 3-step approach: audit → proposal → planning.

**Delivery:** Video conference sessions with a professional coach.

**Pricing:** First 30-minute audit session is free. Subsequent sessions are paid (pricing not publicly listed — determined after initial session).

**Process:**
1. **Audit** — Free 30-minute discovery session to establish goals and experience the coaching process
2. **Proposition** — If the user wants to continue, a tailored coaching plan is proposed
3. **Planification** — First 2 sessions are scheduled; ongoing sessions planned as needed

**Session requirements (communicated to user):**
- Quiet, private space (they need to speak freely)
- Paper/notebook and pen
- Come as they are, no filters

```
[AGENT CONTEXT]
Trigger phrases:
- "coaching", "accompagnement", "objectifs"
- "je suis bloqué", "je ne sais pas comment avancer"
- "développer mon salon", "manager", "gestion d'équipe"

Action: Explain the free initial audit session. Book a discovery call.
```

---

## 12. Formations (Partner Referral)

**What it is:** Government-funded digital training (financed by BPI and FranceNum, no CPF). Covers social media, digital marketing, website creation, and AI — specifically designed for small business owners.

**Delivery:** Online — 2× 3-hour Zoom sessions with a trainer + e-learning platform for replays and exercises. Can also be done 100% via replay.

**Pricing:** Free (100% funded) for eligible businesses.

**Eligibility criteria:**
- Business must be 2+ years old
- Revenue of 15,000€+ in at least one of the last 3 fiscal years
- Fewer than 250 employees
- Not in liquidation
- Not already benefited from 3 accompaniments under this program
- Compliant with de minimis regulations

**Available courses:**
- **Réseaux sociaux** — Social media strategy, content creation, audience growth, sponsored campaigns
- **Marketing digital** — Buyer behaviour, Google tools (My Business, Ads), online reputation, presence unification
- **Création & gestion de site web** — CMS (WordPress), design, SEO, e-commerce, security, maintenance
- **Intelligence Artificielle** — AI for marketing and commercial strategy

```
[AGENT CONTEXT]
Trigger phrases:
- "formation", "se former", "apprendre"
- "réseaux sociaux", "Instagram", "Facebook", "Google My Business"
- "site web", "créer un site", "marketing digital"
- "intelligence artificielle", "IA"
- "gratuit formation", "BPI", "FranceNum"

Qualifying questions:
- "Votre entreprise a-t-elle plus de 2 ans ?"
- "Avez-vous réalisé plus de 15 000€ de CA sur l'un des 3 derniers exercices ?"

Action: Check eligibility, then redirect to the training registration form.
```

---

## 13. Site Internet (Partner Referral)

**What it is:** One-time purchase website creation service — a custom showcase site for the salon.

**Delivery:** Built by a partner agency. One-time payment, no subscription.

**Pricing:**
- **Site internet vitrine sur-mesure:** 149€ (one-time, no subscription)
- **Page Google My Business optimisation:** dès 29€

**Key selling point:** Extremely affordable entry point — no recurring costs.

```
[AGENT CONTEXT]
Trigger phrases:
- "site internet", "site web", "créer un site"
- "présence en ligne", "visibilité", "Google"
- "Google My Business", "fiche Google"

Action: Explain the 149€ one-time offer. Redirect to the partner for project setup.
Note: If the user asks about a more sophisticated site, this may not be sufficient — mention the formation site web as a complement.
```

---

## 14. Plaque NFC — Avis Google/Facebook (Partner Referral)

**What it is:** NFC-enabled plaques that make it easy for salon clients to leave Google or Facebook reviews by tapping their phone.

**Delivery:** Physical product ordered through partner.

**Pricing:** Not listed publicly — obtain quote through ComCoi.

```
[AGENT CONTEXT]
Trigger phrases:
- "avis Google", "avis clients", "NFC"
- "réputation en ligne", "reviews"
- "plaque avis"

Action: Redirect to partner or provide contact info for ordering.
```

---

## 15. Mutuelle (Partner Referral) — DETAILS PENDING

**What it is:** Private health insurance comparison/offering for salon owners and their employees.

**Delivery:** TBD

**Pricing:** TBD

```
[AGENT CONTEXT]
Trigger phrases:
- "mutuelle", "complémentaire santé", "couverture santé"
- "mutuelle entreprise", "mutuelle obligatoire"

Action: Acknowledge the service exists and collect user's contact info for a callback. Service details to be confirmed.
Status: PENDING — awaiting details from Eric.
```

---

## 16. Téléphonie (Partner Referral) — DETAILS PENDING

**What it is:** Telephone/telecommunications provider comparison or preferential rates for salon owners.

**Delivery:** TBD

**Pricing:** TBD

```
[AGENT CONTEXT]
Trigger phrases:
- "téléphone", "téléphonie", "forfait mobile"
- "ligne fixe", "opérateur"

Action: Acknowledge the service exists and collect user's contact info for a callback. Service details to be confirmed.
Status: PENDING — awaiting details from Eric.
```

---

## 17. Juridique — Legal Services Hub (Mixed)

**What it is:** An umbrella category grouping several legal services: company creation (section 6), account approval/filing (section 7), business difficulty support (section 8), and access to partner lawyers.

**Note for the landing page:** This appears as a top-level navigation category in the current Bubble app sidebar ("Juridique"). In the rebuild, this should be a clear section that surfaces the relevant sub-services.

```
[AGENT CONTEXT]
Trigger phrases:
- "juridique", "avocat", "conseil juridique"
- "problème légal", "litige", "contrat"

Action: Clarify what the user needs and route to the appropriate sub-service (création, approbation, difficulté, or partner lawyer referral).
```

---

## 18. Blog / Coiffure Academy (In-App Tool)

**What it is:** Educational blog with articles about salon management, financial advice, industry news, and regulatory updates. Written by Eric and the ComCoi team.

**Delivery:** Free, publicly accessible. Also serves as the knowledge base for the AI financial assistant (RAG pipeline).

**Pricing:** Free

```
[AGENT CONTEXT]
Trigger phrases:
- "article", "blog", "conseil", "information"
- "comment faire", "apprendre à gérer"
- "coiffure academy"

Action: Search blog content for relevant articles. If the question is about financial management, prefer answering directly using the user's data + blog knowledge rather than just linking an article.
```

---

## Cross-Service Routing Logic for the CoCo Agent

When a user describes a problem rather than naming a specific service, the agent should use this routing logic:

| User situation | Primary recommendation | Secondary |
|---|---|---|
| "I don't know if I'm making money" | Rentabilité tool | — |
| "My accountant is too expensive" | Comptabilité en ligne (Noly) | Gestion des factures (to reduce costs with current accountant) |
| "I want to set my prices properly" | Rentabilité tool (pricing calculator) | — |
| "I need to hire someone" | Bulletins de salaire | — |
| "I want to open my own salon" | Création d'entreprise | Coaching |
| "My business is struggling" | Accompagnement entreprises en difficulté | Coaching |
| "I want more clients" | Formations (marketing digital) | Site internet, Google My Business |
| "I'm behind on my accounting" | Comptabilité en retard | — |
| "I want to save money on my bills" | Assurance + Énergie + Mutuelle comparisons | Rentabilité tool (identify other savings) |
| "I need help with my employees" | Bulletins de salaire | Coaching |
| "I need a website" | Site internet (149€) | Formations (création site web) |
| "What legal structure should I choose?" | Création d'entreprise (free consultation) | Business type comparison tool (v2) |

---

## Pricing Summary

### New pricing (from 2026-05)

| Service | Price | Type |
|---|---|---|
| CCPilot (outils de pilotage seuls) | 32€ HT/mois | Subscription |
| PACK BIC + CCPilot | 89€ HT/mois | Subscription |
| PACK BIC+ + CCPilot | 119€ HT/mois | Subscription |
| Comptabilité PACK BIC (seul) | dès 63€ HT/mois | Subscription |
| Comptabilité PACK BIC+ (seul) | dès 93€ HT/mois | Subscription |

### Tarifs préservés — clients historiques uniquement

> Ces tarifs sont conservés pour les clients abonnés avant la restructuration tarifaire de 2026-05.
> **Ne sont jamais proposés à de nouveaux prospects.** CoCo: si un utilisateur mentionne payer 99€/an, c'est son tarif d'origine — ne jamais suggérer de migrer.

| Plan hérité | Tarif d'origine | Note |
|---|---|---|
| ccpilot_annual_99 | 99€ HT/an | Ancien tarif annuel CCPilot |
| bic_monthly_63 | 63€ HT/mois | Ancien PACK BIC seul |
| bic_plus_monthly_93 | 93€ HT/mois | Ancien PACK BIC+ seul |
| bic_plus_monthly_99 | 99€ HT/mois | Ancien PACK BIC+ seul (variante) |

### Autres services

| Service | Price | Type |
|---|---|---|
| Comptabilité PACK BIC | dès 63€ HT/mois | Subscription |
| Comptabilité PACK BIC+ | dès 93€ HT/mois | Subscription |
| Gestion factures BASIC IR | dès 20€ HT/mois | Subscription |
| Gestion factures BASIC IS | dès 25€ HT/mois | Subscription |
| Déclaration des revenus | 10€ HT/mois | Option |
| Dépôt des comptes sociaux | 25€ HT/mois | Option |
| Comptabilité en retard | dès 549€ HT/exercice | One-time |
| Bulletin de salaire — dossier | 65€ HT | One-time |
| Bulletin de salaire — mensuel | dès 24€ HT/salarié/mois | Per unit |
| Création d'entreprise | dès 449€ HT | One-time |
| Accompagnement difficulté | 80€ HT/h | Per session |
| Site internet | 149€ | One-time |
| Google My Business optimisation | dès 29€ | One-time |
| Assurance comparison | Gratuit | Free |
| Énergie comparison | Gratuit | Free |
| Formations (BPI/FranceNum) | Gratuit | Free (funded) |
| Coaching (audit initial) | Gratuit | Free |
| Mutuelle | TBD | TBD |
| Téléphonie | TBD | TBD |
