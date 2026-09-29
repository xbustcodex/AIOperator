package com.primetech.terminal.buster;

import com.primetech.terminal.buster.BusterResult;
import com.primetech.terminal.buster.IBusterBridgeCallback;

interface IBusterBridge {
    void busterStatus(in String correlationId, IBusterBridgeCallback callback);
    void busterServices(in String correlationId, IBusterBridgeCallback callback);
    void busterCapabilities(in String correlationId, IBusterBridgeCallback callback);
    void busterHealth(in String correlationId, IBusterBridgeCallback callback);
    void busterPing(in String correlationId, IBusterBridgeCallback callback);
    void busterServiceStart(in String correlationId, in String serviceName,
                            IBusterBridgeCallback callback);
    void busterServiceRestart(in String correlationId, in String serviceName,
                              IBusterBridgeCallback callback);
    void busterServiceStatus(in String correlationId, in String serviceName,
                             IBusterBridgeCallback callback);
    // Requests presentation of the Buster GUI. It takes no target parameter
    // by design: TerminalP builds the bounded Android action itself, so a
    // caller cannot supply a URL, package, activity or Intent string.
    void busterPresent(in String correlationId, IBusterBridgeCallback callback);
    // --- Phase 5B.1: append-only. The nine operations above are unchanged. ---

    // Reports which modern Buster runtime TerminalP hosts. Read-only: it never
    // installs, updates, starts, stops or modifies Buster. Returns only fields
    // TerminalP can establish authoritatively; unknown fields are omitted
    // rather than fabricated, and no filesystem path is returned.
    void busterDeployment(in String correlationId, IBusterBridgeCallback callback);

    // Reads one bounded Buster informational view. `view` must be one of the
    // closed set the host recognises; anything else is refused before any
    // argument reaches the guest. There is no path, URL, query language or
    // command form, and no way to name a Python function or module.
    void busterRead(in String correlationId, in String view,
                    IBusterBridgeCallback callback);
}
