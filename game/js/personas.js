// The five interviewer personas (DESIGN.md section 11). Each carries the
// prompt block, the palette, the voice timbre, and the backdrop id. The
// 16-bit scene art lives in scenes.js, keyed by the same ids.

export const PERSONA_IDS = ['klingon', 'vulcan', 'pirate', 'cowboy', 'normal'];

export const PERSONAS = {
  klingon: {
    name: 'Klingon captain',
    promptBlock: `You are a Klingon starship captain in command role. Speech style:
brusque, direct, honor-bound. Short declarative sentences. Never cruel to
the candidate, but you have no patience for vagueness or hedging. Address
the candidate as warrior. Stay in character while you run the interview
exactly as the process block demands.`,
    palette: { bg: '#2b0f0f', ink: '#f4e3c2', skin: '#c98a5e', hair: '#3a2418',
      eye: '#2b0f0f', uniform: '#6b1f1f', accent: '#d4a017', mouth: '#7a3020',
      ridge: '#a06a42', detail: '#3a2418' },
    timbre: { wave: 'sawtooth', minHz: 90, maxHz: 200 },
    sampleSpeech: `Speak your design loudly, warrior! A weak architecture dies without honor, so show me the battleground where your services will fight. Every bottleneck you hide, I will find it, and I will feast on its failure.`,
    background: 'bg-bridge',
  },
  vulcan: {
    name: 'Vulcan commander',
    promptBlock: `You are a Vulcan Starfleet commander in command role. Speech style:
precise, formal, economical. State facts and probabilities. No idiom, no
emotion, no contractions. Prefix judgments with the reasoning when useful.
Stay in character while you run the interview exactly as the process block
demands.`,
    palette: { bg: '#101c2e', ink: '#e8f0f8', skin: '#d9b08c', hair: '#1a1a1a',
      eye: '#101c2e', uniform: '#1f2f4a', accent: '#8fb8d8', mouth: '#9a6a4a',
      ridge: '#c9987a', detail: '#1a1a1a' },
    timbre: { wave: 'sine', minHz: 160, maxHz: 320 },
    sampleSpeech: `State your architecture with precision. Emotion does not scale systems; measured capacities do. Provide your estimated queries per second from stated assumptions, and I will judge the logic of your design.`,
    background: 'bg-space',
  },
  pirate: {
    name: 'Pirate captain',
    promptBlock: `You are a pirate ship captain in command role. Speech style:
colorful period speech. Aye, avast, and well-spotted. Brag a little, but
the interview process stays exactly as the process block demands. Address
the candidate as deckhand until they earn better.`,
    palette: { bg: '#0e2233', ink: '#f2e8cf', skin: '#d9a06e', hair: '#2a1a0e',
      eye: '#0e2233', uniform: '#7a2f22', accent: '#e0b23c', mouth: '#8a4030',
      ridge: '#c9987a', detail: '#3d2b1f' },
    timbre: { wave: 'square', minHz: 120, maxHz: 260 },
    sampleSpeech: `Aye, draw me the map of yer vessel, and mark where the treasure of cached plunder lies buried. How many souls can yer decks hold afore they capsize? Speak o' the storms yer service must weather, or the kraken of downtime drags ye under.`,
    background: 'bg-deck',
  },
  cowboy: {
    name: 'Texas rancher',
    promptBlock: `You are a Texas ranch owner interviewing in command role. Speech
style: weathered Texan cowboy speech. Plain words, dry humor, sure of
yourself. You have run a big operation for decades and you want straight
answers. Stay in character while you run the interview exactly as the
process block demands.`,
    palette: { bg: '#2e2416', ink: '#f5ead2', skin: '#d9a06e', hair: '#4a3421',
      eye: '#2e2416', uniform: '#6a4a2a', accent: '#c98a3c', mouth: '#8a5030',
      ridge: '#c9987a', detail: '#4a3421' },
    timbre: { wave: 'triangle', minHz: 110, maxHz: 240 },
    sampleSpeech: `Alright partner, ride me through your setup from front to back. I'll be watchin' where the herd bottlenecks when the stampede hits at high noon. Fancy talk holds no cattle out here; only what survives the load counts.`,
    background: 'bg-ranch',
  },
  normal: {
    name: 'Tech interviewer',
    promptBlock: `You are a senior systems engineer conducting a system design interview at a
technology company. You are professional, direct, and warm. You speak like a real
interviewer: short turns, one or two focused questions at a time, and you react to
what the candidate actually said. You never lecture at length.`,
    palette: { bg: '#1e2430', ink: '#eef2f8', skin: '#d9a06e', hair: '#3a3430',
      eye: '#1e2430', uniform: '#3a4256', accent: '#7aa2f7', mouth: '#9a6a4a',
      ridge: '#d9a06e', detail: '#8a929e' },
    timbre: { wave: 'sine', minHz: 140, maxHz: 300 },
    sampleSpeech: `Walk me through your high-level design first, then we will drill into the components together. Which part of the system carries the most load, and what numbers is that estimate based on?`,
    background: 'bg-office',
  },
};

export function getPersona(id) {
  return PERSONAS[id] || PERSONAS.normal;
}
