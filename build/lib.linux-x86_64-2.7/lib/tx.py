# Copyright (c) 2016-2017, Neil Booth
# Copyright (c) 2017, the ElectrumX authors
#
# All rights reserved.
#
# The MIT License (MIT)
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# and warranty status of this software.

'''Transaction-related classes and functions.'''


from collections import namedtuple

from lib.hash import double_sha256, hash_to_str
from lib.util import (cachedproperty, unpack_int32_from, unpack_int64_from,
                      unpack_uint16_from, unpack_uint32_from,
                      unpack_uint64_from)


class Tx(namedtuple("Tx", "version inputs outputs locktime")):
    '''Class representing a transaction.'''

    @cachedproperty
    def is_coinbase(self):
        return self.inputs[0].is_coinbase

    # FIXME: add hash as a cached property?


class TxInput(namedtuple("TxInput", "prev_hash prev_idx script sequence")):
    '''Class representing a transaction input.'''

    ZERO = bytes(32)
    MINUS_1 = 4294967295

    @cachedproperty
    def is_coinbase(self):
        return (self.prev_hash == TxInput.ZERO and
                self.prev_idx == TxInput.MINUS_1)

    def __str__(self):
        script = self.script.hex()
        prev_hash = hash_to_str(self.prev_hash)
        return ("Input({}, {:d}, script={}, sequence={:d})"
                .format(prev_hash, self.prev_idx, script, self.sequence))


class TxOutput(namedtuple("TxOutput", "value pk_script")):
    pass


class Deserializer(object):
    '''Deserializes blocks into transactions.

    External entry points are read_tx() and read_block().

    This code is performance sensitive as it is executed 100s of
    millions of times during sync.
    '''

    def __init__(self, binary, start=0):
        assert isinstance(binary, bytes)
        self.binary = binary
        self.binary_length = len(binary)
        self.cursor = start

    def read_tx(self):
        '''Return a (Deserialized TX, TX_HASH) pair.

        The hash needs to be reversed for human display; for efficiency
        we process it in the natural serialized order.
        '''
        start = self.cursor
        return Tx(
            self._read_le_int32(),  # version
            self._read_inputs(),    # inputs
            self._read_outputs(),   # outputs
            self._read_le_uint32()  # locktime
        ), double_sha256(self.binary[start:self.cursor])

    def read_tx_block(self):
        '''Returns a list of (deserialized_tx, tx_hash) pairs.'''
        read_tx = self.read_tx
        txs = [read_tx() for _ in range(self._read_varint())]
        # Some coins have excess data beyond the end of the transactions
        return txs

    def _read_inputs(self):
        read_input = self._read_input
        return [read_input() for i in range(self._read_varint())]

    def _read_input(self):
        return TxInput(
            self._read_nbytes(32),   # prev_hash
            self._read_le_uint32(),  # prev_idx
            self._read_varbytes(),   # script
            self._read_le_uint32()   # sequence
        )

    def _read_outputs(self):
        read_output = self._read_output
        return [read_output() for i in range(self._read_varint())]

    def _read_output(self):
        return TxOutput(
            self._read_le_int64(),  # value
            self._read_varbytes(),  # pk_script
        )

    def _read_byte(self):
        cursor = self.cursor
        self.cursor += 1
        return self.binary[cursor]

    def _read_nbytes(self, n):
        cursor = self.cursor
        self.cursor = end = cursor + n
        assert self.binary_length >= end
        return self.binary[cursor:end]

    def _read_varbytes(self):
        return self._read_nbytes(self._read_varint())

    def _read_varint(self):
        n = self.binary[self.cursor]
        self.cursor += 1
        if n < 253:
            return n
        if n == 253:
            return self._read_le_uint16()
        if n == 254:
            return self._read_le_uint32()
        return self._read_le_uint64()

    def _read_le_int32(self):
        result, = unpack_int32_from(self.binary, self.cursor)
        self.cursor += 4
        return result

    def _read_le_int64(self):
        result, = unpack_int64_from(self.binary, self.cursor)
        self.cursor += 8
        return result

    def _read_le_uint16(self):
        result, = unpack_uint16_from(self.binary, self.cursor)
        self.cursor += 2
        return result

    def _read_le_uint32(self):
        result, = unpack_uint32_from(self.binary, self.cursor)
        self.cursor += 4
        return result

    def _read_le_uint64(self):
        result, = unpack_uint64_from(self.binary, self.cursor)
        self.cursor += 8
        return result

class TxTime(namedtuple("Tx", "version time inputs outputs locktime")):
    '''Class representing transaction that has a time field.'''

    @cachedproperty
    def is_coinbase(self):
        return self.inputs[0].is_coinbase


class DeserializerTxTime(Deserializer):
    def read_tx(self):
        start = self.cursor

        return TxTime(
            self._read_le_int32(),  # version
            self._read_le_uint32(), # time
            self._read_inputs(),    # inputs
            self._read_outputs(),   # outputs
            self._read_le_uint32(), # locktime
        ), double_sha256(self.binary[start:self.cursor])
