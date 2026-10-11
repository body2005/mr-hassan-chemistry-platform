// hls.js ships shared public types but no separate declaration for ./light.
// Only the core transport/ABR API is used by our H.264/AAC lesson player.
declare module 'hls.js/light' {
  export { default } from 'hls.js';
}
