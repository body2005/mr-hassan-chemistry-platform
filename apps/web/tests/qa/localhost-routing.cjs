// Docker Desktop's gateway is routing, not a TLS exception. Keep the URL and
// hostname verification as localhost; the test browser uses the same mapping.
const dns = require('node:dns');
if (process.env.QA_ROUTE_LOCALHOST) {
  if (process.env.QA_PROJECT !== 'chemistryaudit2' || process.env.QA_ROUTE_LOCALHOST !== 'host.docker.internal') {
    throw new Error('Localhost routing is restricted to the isolated QA runner');
  }
  const lookup = dns.lookup;
  dns.lookup = function (hostname, ...args) {
    return lookup.call(dns, hostname === 'localhost' ? 'host.docker.internal' : hostname, ...args);
  };
  // Playwright's Happy Eyeballs transport uses the Promise API separately.
  // Keep all/family/options and TLS hostname checks unchanged.
  const promiseLookup = dns.promises.lookup;
  dns.promises.lookup = function (hostname, ...args) {
    return promiseLookup.call(dns.promises, hostname === 'localhost' ? 'host.docker.internal' : hostname, ...args);
  };
}
