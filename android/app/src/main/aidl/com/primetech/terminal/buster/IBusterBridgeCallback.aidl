package com.primetech.terminal.buster;

import com.primetech.terminal.buster.BusterResult;

interface IBusterBridgeCallback {
    oneway void onResult(in BusterResult result);
}
