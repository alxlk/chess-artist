"""
A. Program name
Chess Artist

B. Program description
It is a python script that can annotate a chess pgn file with
static evaluation of an engine.

C. License notice
This program is free software, you can redistribute it and/or modify
it under the terms of the GPLv3 License as published by the
Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY. See the GNU General Public License
for more details.

You should have received a copy of the GNU General Public License (LICENSE)
along with this program, if not visit https://www.gnu.org/licenses/gpl.html

D. Dependent modules and/or programs
1. python-chess
https://pypi.python.org/pypi/python-chess

E. Programming language
1. Python v2.7.11
https://www.python.org/

F. Other
1. See also the README.txt for some useful informations.
"""

import subprocess
import os
import sys
import time
import chess
from chess import pgn

# Constants
APP_NAME = 'Chess Artist'
APP_VERSION = '0.1.0'
BOOK_MOVE_LIMIT = 30
BOOK_SEARCH_TIME = 200
MAX_SCORE = 32000
TEST_SEARCH_SCORE = 100000
TEST_SEARCH_DEPTH = 1000
EPD_FILE = 1
PGN_FILE = 2
WIN_SCORE = 6.0

def PrintProgram():
    """ Prints program name and version """
    print('%s %s\n' %(APP_NAME, APP_VERSION))
    
def DeleteFile(fn):
    """ Delete fn file """
    if os.path.isfile(fn):
        os.remove(fn)

def CheckFiles(infn, outfn, engfn):
    """ Quit program if infn is missing.
        Quit program if infn and outfn is the same.
        Quit program if engfn is missing.
        Quit program if input file type is not epd or pgn
    """
    # input file is missing
    if not os.path.isfile(infn):
        print('Error! %s is missing' %(infn))
        sys.exit(1)

    # input file and output file is the same.
    if infn == outfn:
        print('Error! input filename and output filename is the same')
        sys.exit(1)

    # engine file is missing.
    if not os.path.isfile(engfn):
        print('Error! %s is missing' %(engfn))
        sys.exit(1)

    # If file is not epd or pgn
    if not infn.endswith('.epd') and not infn.endswith('.pgn'):
        print('Error! %s is not an epd or pgn file' %(infn))
        sys.exit(1)

def EvaluateOptions(opt):
    """ Convert opt list to dict and returns it """
    return dict([(k, v) for k, v in zip(opt[::2], opt[1::2])])

def GetOptionValue(opt, optName, var):
    """ Returns value of opt dict given the key """
    if opt.has_key(optName):
        var = opt.get(optName)
        if optName == '-movetime':
            var = int(var)
        elif optName == '-enghash':
            var = int(var)
        elif optName == '-engthreads':
            var = int(var)
        elif optName == '-movestart':
            var = int(var)
    return var

class Analyze():
    """ An object that will read and annotate games in a pgn file """
    def __init__(self, infn, outfn, eng, **opt):
        """ Initialize """
        self.infn = infn
        self.outfn = outfn
        self.eng = eng
        self.bookOpt = opt['-book']
        self.evalOpt = opt['-eval']
        self.moveTimeOpt = opt['-movetime']
        self.engHashOpt = opt['-enghash']
        self.engThreadsOpt = opt['-engthreads']
        self.moveStartOpt = opt['-movestart']
        self.jobOpt = opt['-job']
        self.writeCnt = 0
        self.engIdName = self.GetEngineIdName()

    def UciToSanMove(self, pos, uciMove):
        """ Returns san move given uci move """
        board = chess.Board(pos)
        board.push(chess.Move.from_uci(uciMove))
        sanMove = board.san(board.pop())
        return sanMove

    def PrintEngineIdName(self):
        """ Prints engine id name """
        print('Analyzing engine: %s' %(self.engIdName))

    def GetGoodNag(self, side, posScore, engScore, complexityNumber, moveChanges):
        """ Returns !!, !, !? depending on the player score, analyzing engine score,
            complexity number and pv move changes.
        """
        # Convert the posScore and engScore to side POV
        # to easier calculate the move NAG = Numeric Annotation Glyphs.
        if not side:
            posScore = -1 * posScore
            engScore = -1 * engScore

        # Set default NAG, GUI will not display this.
        moveNag = '$0'
        
        # Very good !!
        if posScore > engScore and\
           moveChanges >= 4 and\
           complexityNumber >= 45 and\
           posScore >= +0.75 and\
           posScore <= +3.0:
            moveNag = '$3'
            
        # Good !
        elif moveChanges >= 3 and\
             complexityNumber >= 30 and\
             posScore >= -0.15 and\
             posScore <= +3.0:
            moveNag = '$1'
            
        # Interesting !?
        elif moveChanges >= 2 and\
             complexityNumber >= 20 and\
             posScore >= -0.15 and\
             posScore <= +3.0:
            moveNag = '$5'
        return moveNag

    def GetBadNag(self, side, posScore, engScore):
        """ Returns ??, ?, ?! depending on the player score and analyzing engine score.
            posScore is the score of the move in the game, in pawn unit.
            engScore is the score of the move suggested by the engine, in pawn unit.
            Positive score is better for white and negative score is better for black, (WPOV).
            Scoring range from white's perspective:
            Blunder: posScore < -1.50
            Mistake: posScore >= -1.50 and posScore < -0.75
            Dubious: posScore >= -0.75 and posScore < -0.15
            Even   : posScore >= -0.15 and posScore <= +0.15
            Special condition:
            1. If engine score is winning but player score is not winning,
            consider this as a mistake.
            Mistake: engScore > +1.50 and posScore < +1.50
        """
        # Convert the posScore and engScore to side POV
        # to easier calculate the move NAG = Numeric Annotation Glyphs.
        if not side:
            posScore = -1 * posScore
            engScore = -1 * engScore

        # Set default NAG, GUI will not display this.
        moveNag = '$0'
        
        # Blunder ??
        if posScore < -1.50 and engScore >= -1.50:
            moveNag = '$4'
            
        # Mistake ?
        elif posScore < -0.75 and engScore >= -0.75:
            moveNag = '$2'
            
        # Dubious ?!
        elif posScore < -0.15 and engScore >= -0.15:
            moveNag = '$6'

        # Mistake ? if engScore is winning and posScore is not winning
        elif engScore > +1.50 and posScore <= +1.50:
            moveNag = '$2'

        # Special case, when player score is greater than or
        # equal to engine score, give an interesting symbol !?
        if posScore >= engScore:
            moveNag = '$5'
        return moveNag            

    def WriteSanMove(self, side, moveNumber, sanMove):
        """ Write moves only in the output file """
        # Write the moves
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1
            if side:
                f.write('%d. %s ' %(moveNumber, sanMove))
            else:
                f.write('%s ' %(sanMove))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 4:
                    self.writeCnt = 0
                    f.write('\n')

    def WritePosScore(self, side, moveNumber, sanMove, posScore):
        """ Write moves with score in the output file """
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                f.write('%d. %s {%+0.2f} ' %(moveNumber, sanMove, posScore))
            else:
                f.write('%s {%+0.2f} ' %(sanMove, posScore))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 4:
                    self.writeCnt = 0
                    f.write('\n')

    def WritePosScoreEngMove(self, side, moveNumber, sanMove, posScore, engMove, engScore,
                             complexityNumber, moveChanges):
        """ Write moves with score and engMove in the output file """
        engShortName = self.engIdName.split()[0]
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                if sanMove != engMove:
                    moveNag = self.GetBadNag(side, posScore, engScore)                    

                    # Write moves and comments
                    f.write('%d. %s %s {%+0.2f} (%d. %s {%+0.2f - %s}) ' %(moveNumber, sanMove, moveNag, posScore,
                                                                          moveNumber, engMove, engScore, engShortName))
                else:
                    moveNag = self.GetGoodNag(side, posScore, engScore, complexityNumber, moveChanges)
                    f.write('%d. %s %s {%+0.2f} ' %(moveNumber, sanMove, moveNag, posScore))
            else:
                if sanMove != engMove:
                    moveNag = self.GetBadNag(side, posScore, engScore)

                    # Write moves and comments  
                    f.write('%d... %s %s {%+0.2f} (%d... %s {%+0.2f - %s}) ' %(moveNumber, sanMove, moveNag, posScore,
                                                                           moveNumber, engMove, engScore, engShortName))
                else:
                    moveNag = self.GetGoodNag(side, posScore, engScore, complexityNumber, moveChanges)
                    f.write('%s %s {%+0.2f} ' %(sanMove, moveNag, posScore))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 2:
                    self.writeCnt = 0
                    f.write('\n')

    def WriteBookMove(self, side, moveNumber, sanMove, bookMove):
        """ Write moves with book moves in the output file """
        bookComment = 'cerebellum'
        assert bookMove is not None
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                f.write('%d. %s (%d. %s {%s}) ' %(moveNumber, sanMove, moveNumber, bookMove, bookComment))
            else:
                f.write('%d... %s (%d... %s {%s}) ' %(moveNumber, sanMove, moveNumber, bookMove, bookComment))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 2:
                    self.writeCnt = 0
                    f.write('\n')

    def WritePosScoreBookMove(self, side, moveNumber, sanMove, bookMove, posScore):
        """ Write moves with score and book moves in the output file """
        bookComment = 'cerebellum'
        assert bookMove is not None
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                f.write('%d. %s {%+0.2f} (%d. %s {%s}) ' %(moveNumber, sanMove, posScore, moveNumber, bookMove, bookComment))
            else:
                f.write('%d... %s {%+0.2f} (%d... %s {%s}) ' %(moveNumber, sanMove, posScore, moveNumber, bookMove, bookComment))
                
                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 2:
                    self.writeCnt = 0
                    f.write('\n') 

    def WritePosScoreBookMoveEngMove(self, side, moveNumber, sanMove, bookMove, posScore, engMove, engScore):
        """ Write moves with score and book moves in the output file """
        bookComment = 'cerebellum'
        assert bookMove is not None
        engShortName = self.engIdName.split()[0]
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                if sanMove != engMove:
                    moveNag = self.GetBadNag(side, posScore, engScore)   

                    # Write moves and comments
                    f.write('%d. %s %s {%+0.2f} (%d. %s {%s}) (%d. %s {%+0.2f - %s}) ' %(moveNumber, sanMove, moveNag, posScore,
                                                                                      moveNumber, bookMove, bookComment,
                                                                                      moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d. %s {%+0.2f} (%d. %s {%s}) ' %(moveNumber, sanMove, posScore, moveNumber, bookMove, bookComment))
            else:
                if sanMove != engMove:
                    moveNag = self.GetBadNag(side, posScore, engScore)

                    # Write moves and comments
                    f.write('%d... %s %s {%+0.2f} (%d... %s {%s}) (%d... %s {%+0.2f - %s}) ' %(moveNumber, sanMove, moveNag, posScore,
                                                                                       moveNumber, bookMove, bookComment,
                                                                                       moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d... %s {%+0.2f} (%d... %s {%s}) ' %(moveNumber, sanMove, posScore, moveNumber, bookMove, bookComment))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 2:
                    self.writeCnt = 0
                    f.write('\n')

    def WriteBookMoveEngMove(self, side, moveNumber, sanMove, bookMove, engMove, engScore):
        """ Write moves with book moves and eng moves in the output file """
        bookComment = 'cerebellum'
        assert bookMove is not None
        engShortName = self.engIdName.split()[0]
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:
            self.writeCnt += 1

            # If side to move is white
            if side:
                if sanMove != engMove:
                    # Write moves and comments
                    f.write('%d. %s (%d. %s {%s}) (%d. %s {%+0.2f - %s}) ' %(moveNumber, sanMove,
                                                        moveNumber, bookMove, bookComment,
                                                        moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d. %s (%d. %s {%s}) ' %(moveNumber, sanMove,
                                                      moveNumber, bookMove, bookComment))
            else:
                if sanMove != engMove:
                    
                    # Write moves and comments
                    f.write('%d... %s (%d... %s {%s}) (%d... %s {%+0.2f - %s}) ' %(moveNumber, sanMove,
                                                        moveNumber, bookMove, bookComment,
                                                        moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d... %s {%+0.2f} (%d... %s {%s}) ' %(moveNumber, sanMove,
                                                        posScore, moveNumber, bookMove, bookComment))

                # Format output, don't write movetext in one long line.
                if self.writeCnt >= 2:
                    self.writeCnt = 0
                    f.write('\n')

    def WriteEngMove(self, side, moveNumber, sanMove, bookMove, engMove, engScore):
        """ Write moves with eng moves in the output file """
        engShortName = self.engIdName.split()[0]
        
        # Write the move and comments
        with open(self.outfn, 'a+') as f:

            # If side to move is white
            if side:
                if sanMove != engMove:
                    # Write moves and comments
                    f.write('%d. %s (%d. %s {%+0.2f - %s}) ' %(moveNumber, sanMove,
                                                        moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d. %s ' %(moveNumber, sanMove))
            else:
                if sanMove != engMove:
                    
                    # Write moves and comments
                    f.write('%d... %s (%d... %s {%+0.2f - %s}) ' %(moveNumber, sanMove,
                                                        moveNumber, engMove, engScore, engShortName))
                else:
                    f.write('%d... %s ' %(moveNumber, sanMove))

    def WriteNotation(self, side, fmvn, sanMove, bookMove,
                      posScore, isGameOver, engMove, engScore,
                      complexityNumber, moveChanges):
        """ Write moves and comments to the output file """
        # (0) If game is over [mate, stalemate] just print the move.
        if isGameOver:
            self.WriteSanMove(side, fmvn, sanMove)
            return

        # (1) Write sanMove, posScore
        isWritePosScore = posScore is not None and\
                       bookMove is None and\
                       engMove is None
        if isWritePosScore:
            self.WritePosScore(side, fmvn, sanMove, posScore)
            return

        # (2) Write sanMove, posScore, bookMove
        isWritePosScoreBook = posScore is not None and\
                              bookMove is not None and\
                              engMove is None
        if isWritePosScoreBook:
            self.WritePosScoreBookMove(side, fmvn, sanMove, bookMove, posScore)
            return

        # (3) Write sanMove, posScore and engMove
        isWritePosScoreEngMove = posScore is not None and\
                       bookMove is None and\
                       engMove is not None
        if isWritePosScoreEngMove:
            self.WritePosScoreEngMove(side, fmvn, sanMove, posScore, engMove, engScore,
                                      complexityNumber, moveChanges)
            return

        # (4) Write sanMove, posScore, bookMove and engMove
        isWritePosScoreBookEngMove = posScore is not None and\
                              bookMove is not None and\
                              engMove is not None
        if isWritePosScoreBookEngMove:
            self.WritePosScoreBookMoveEngMove(side, fmvn, sanMove, bookMove, posScore, engMove, engScore)
            return

        # (5) Write sanMove, bookMove
        isWriteBook = posScore is None and\
                      bookMove is not None and\
                      engMove is None
        if isWriteBook:
            self.WriteBookMove(side, fmvn, sanMove, bookMove)
            return

        # (6) Write sanMove, bookMove and engMove
        isWriteBookEngMove = posScore is None and\
                              bookMove is not None and\
                              engMove is not None
        if isWriteBookEngMove:
            self.WriteBookMoveEngMove(side, fmvn, sanMove, bookMove, engMove, engScore)
            return

        # (7) Write sanMove, engMove
        isWriteEngMove = posScore is None and\
                              bookMove is None and\
                              engMove is not None
        if isWriteEngMove:
            self.WriteEngMove(side, fmvn, sanMove, engMove, engScore)
            return

        # (8) Write sanMove only
        if posScore is None and bookMove is None:
            self.WriteSanMove(side, fmvn, sanMove)
            return            
            
    def MateDistanceToValue(self, d):
        """ Returns value given distance to mate """
        value = 0
        if d < 0:
            value = -2*d - MAX_SCORE
        elif d > 0:
            value = MAX_SCORE - 2*d + 1
        return value

    def GetEngineIdName(self):
        """ Returns the engine id name """
        engineIdName = self.eng[0:-4]

        # Run the engine
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()

            # Save id name.
            if 'id name ' in line:
                idName = line.split()
                engineIdName = ' '.join(idName[2:])            
            if "uciok" in line:           
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()
        return engineIdName

    def GetCerebellumBookMove(self, pos):
        """ Returns a move from cerebellum book """
        isInfoDepth = False
        
        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "uciok" in line:
                break

        # Set the path of Brainfish cerebellum book. Make sure the Brainfish engine,
        # the script and the cerebellum book are on the same directory.
        p.stdin.write("setoption name BookPath value Cerebellum_Light.bin\n")

        # Set threads to 1 just in case the default threads is changed in the future.
        p.stdin.write("setoption name Threads value 1\n")
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("go movetime %d\n" %(BOOK_SEARCH_TIME))

        # Parse the output and extract the bestmove.
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()
            
            # If the engine shows info depth ... it is no longer using a book
            if 'info depth' in line:
                isInfoDepth = True
            
            # Break search when we receive bestmove string from engine
            if 'bestmove ' in line:
                moveLine = line.split()[1]
                bestMove = moveLine.strip()
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()

        # If we did not get info depth from the engine
        # then the bestmove is from the book.
        if not isInfoDepth:
            # Convert uci move to san move format.
            bestMove = self.UciToSanMove(pos, bestMove)
            return bestMove
        return None

    def GetStaticEvalAfterMove(self, pos):
        """ Returns static eval by running the engine,
            setup position pos and send eval command.
        """
        score = TEST_SEARCH_SCORE

        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "uciok" in line:
                break
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("eval\n")

        # Parse the output and extract the engine static eval.
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()
            if 'Total Evaluation: ' in line:
                first = line.split('(')[0]
                score = float(first.split()[2])
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()
        assert score != TEST_SEARCH_SCORE, 'Error! something is wrong in static eval calculation.'
        return score

    def GetSearchScoreBeforeMove(self, pos, side):
        """ Returns search bestmove and score from the engine. """

        # Initialize
        scoreCp = TEST_SEARCH_SCORE

        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "uciok" in line:
                break

        # Set Hash and Threads options to uci engine
        p.stdin.write("setoption name Hash value %d\n" %(self.engHashOpt))
        p.stdin.write("setoption name Threads value %d\n" %(self.engThreadsOpt))
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("go movetime %d\n" %(self.moveTimeOpt))

        # Parse the output and extract the engine search score.
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()
            if 'score cp ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                scoreCp = int(splitStr[scoreIndex + 2])
            if 'score mate ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                mateInN = int(splitStr[scoreIndex + 2])

                # Convert mate in move number to value
                scoreCp = self.MateDistanceToValue(mateInN)        
                
            # Break search when we receive bestmove string from engine
            if 'bestmove ' in line:
                bestMove = line.split()[1]
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()        
        assert scoreCp != TEST_SEARCH_SCORE, 'Error, search failed to return a score.'

        # Convert uci move to san move format.
        bestMove = self.UciToSanMove(pos, bestMove)

        # Convert score from the point of view of white.
        if not side:
            scoreCp = -1 * scoreCp

        # Convert the score to pawn unit in float type
        scoreP = float(scoreCp)/100.0
        return bestMove, scoreP

    def GetComplexityNumber(self, savedMove):
        """ Returns complexity number and move changes counts """
        complexityNumber, moveChanges = 0, 0
        for n in savedMove:
            depth = n[0]
            if depth >= 10:
                if n[1] != lastMove and depth != lastDepth:
                    complexityNumber += n[0]
                    moveChanges += 1
            lastDepth = depth
            lastMove = n[1]
        return complexityNumber, moveChanges

    def GetSearchScoreAfterMove(self, pos, side):
        """ Returns search's score, complexity number and pv move changes counts. """
        # Initialize
        scoreCp = TEST_SEARCH_SCORE
        searchDepth = 0
        savedMove = []
        complexityNumber = 0
        moveChanges = 0;
        isGetComplexityNumber = self.jobOpt == 'analyze' and\
                                self.moveTimeOpt >= 2000

        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "uciok" in line:
                break

        # Set Hash and Threads options to uci engine
        p.stdin.write("setoption name Hash value %d\n" %(self.engHashOpt))
        p.stdin.write("setoption name Threads value %d\n" %(self.engThreadsOpt))
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("go movetime %d\n" %(self.moveTimeOpt))

        # Parse the output and extract the engine search score.
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()

            # Save pv move per depth
            if isGetComplexityNumber:
                if 'info depth ' in line and 'pv ' in line and not\
                   'upperbound' in line and not 'lowerbound' in line:

                    # Get the depth
                    splitLine = line.split()
                    searchDepth = int(splitLine[splitLine.index('depth')+1])

                    # Get the move and save it
                    pvMove = splitLine[splitLine.index('pv')+1].strip()
                    savedMove.append([searchDepth, pvMove])
                
            if 'score cp ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                scoreCp = int(splitStr[scoreIndex + 2])
            if 'score mate ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                mateInN = int(splitStr[scoreIndex + 2])

                # Convert mate in move number to value
                scoreCp = self.MateDistanceToValue(mateInN)        
                
            # Break search when we receive bestmove string from engine
            if 'bestmove ' in line:
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()        
        assert scoreCp != TEST_SEARCH_SCORE, 'Error, search failed to return a score.'

        # Get complexity number and moveChanges count
        if isGetComplexityNumber:
            complexityNumber, moveChanges = self.GetComplexityNumber(savedMove)
            
        # Invert the score sign because we analyze the position after the move.
        scoreCp = -1 * scoreCp

        # Convert score from the point of view of white.
        if not side:
            scoreCp = -1 * scoreCp

        # Convert the score to pawn unit in float type
        scoreP = float(scoreCp)/100.0
        return scoreP, complexityNumber, moveChanges

    def GetEpdEngineSearchScore(self, pos):
        """ Returns acd, acs, bm, ce and Ae op codes. """

        # Initialize
        bestMove = None
        scoreCp = TEST_SEARCH_SCORE
        depthSearched = TEST_SEARCH_DEPTH

        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()               
            if "uciok" in line:
                break

        # Set Hash and Threads options to uci engine
        p.stdin.write("setoption name Hash value %d\n" %(self.engHashOpt))
        p.stdin.write("setoption name Threads value %d\n" %(self.engThreadsOpt))
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("go movetime %d\n" %(self.moveTimeOpt))

        # Parse the output and extract the engine search score, depth and bestmove
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()
            if 'score cp ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                scoreCp = int(splitStr[scoreIndex + 2])
            if 'score mate ' in line:
                splitStr = line.split()
                scoreIndex = splitStr.index('score')
                mateInN = int(splitStr[scoreIndex + 2])
                
                # Convert mate in move number to value
                scoreCp = self.MateDistanceToValue(mateInN)
            if 'depth ' in line:
                splitStr = line.split()
                depthIndex = splitStr.index('depth')
                depthSearched = int(splitStr[depthIndex + 1])                     

            # Break search when we receive bestmove
            if 'bestmove ' in line:
                bestMove = line.split()[1]
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()

        # Convert uci move to san move format.
        bestMove = self.UciToSanMove(pos, bestMove)

        # Verify values to be returned
        assert depthSearched != TEST_SEARCH_DEPTH, 'Error the engine does not search at all.'
        assert scoreCp != TEST_SEARCH_SCORE, 'Error!, search failed to return a score.'
        assert bestMove is not None, 'Error! seach failed to return a move.'
        return depthSearched, self.moveTimeOpt/1000, bestMove, scoreCp

    def GetEpdEngineStaticScore(self, pos):
        """ Returns ce and Ae op codes. """

        # Initialize
        scoreP = TEST_SEARCH_SCORE

        # Run the engine.
        p = subprocess.Popen(self.eng, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        # Send command to engine.
        p.stdin.write("uci\n")

        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()               
            if "uciok" in line:
                break
                
        # Send command to engine.
        p.stdin.write("isready\n")
        
        # Parse engine replies.
        for eline in iter(p.stdout.readline, ''):
            line = eline.strip()
            if "readyok" in line:
                break
                
        # Send commands to engine.
        p.stdin.write("ucinewgame\n")
        p.stdin.write("position fen " + pos + "\n")
        p.stdin.write("eval\n")

        # Parse the output and extract the engine search score, depth and bestmove
        for eline in iter(p.stdout.readline, ''):        
            line = eline.strip()                  

            # Break search
            if 'Total Evaluation: ' in line:
                first = line.split('(')[0]
                scoreP = float(first.split()[2])
                break
                
        # Quit the engine
        p.stdin.write('quit\n')
        p.communicate()

        # Verify values to be returned
        assert scoreP != TEST_SEARCH_SCORE, 'Error!, engine failed to return its static eval.'

        # Convert to side POV
        if pos.split()[1] == 'b':
            scoreP = -1 * scoreP

        # Convert to centipawn
        scoreCp = int(scoreP * 100.0)
        return scoreCp
    
    def AnnotatePgn(self):
        """ Parse the pgn file and annotate the games """
        # Get engine id name for the Annotator tag.
        engineIdName = self.engIdName

        # Disable bookOpt if engine is not Brainfish.
        if self.bookOpt == 'cerebellum':
            if 'Brainfish' not in engineIdName:
                self.bookOpt = 'none'
                print('\nWarning!! engine is not Brainfish, cerebellum book is disabled.\n')
        
        # Open the input pgn file
        pgnHandle = open(self.infn, 'r')

        # Read the input pgn file using the python-chess module.
        game = chess.pgn.read_game(pgnHandle)

        # Used for displaying progress in console.
        gameCnt = 0

        # Loop thru the games.
        while game:
            gameCnt += 1

            # Used for formatting the output.
            self.writeCnt = 0

            # Show progress in console.
            print('Annotating game %d...' %(gameCnt))

            # We don't access cere book if isCereEnd is true.
            isCereEnd = False

            # Save the tag section of the game.
            for key, value in game.headers.items():
                with open(self.outfn, 'a+') as f:
                    f.write('[%s \"%s\"]\n' %(key, value))

            # Write the annotator tag.
            with open(self.outfn, 'a+') as f:
                f.write('[Annotator "%s"]\n\n' %(engineIdName))

            # Before the movetext are written, add a comment of whether
            # move comments are from static evaluation or search score of the engine.
            if self.evalOpt == 'static':
                with open(self.outfn, 'a+') as f:
                    f.write('{Move comments are from engine static evaluation.}\n')
            elif self.evalOpt == 'search':
                with open(self.outfn, 'a+') as f:
                    f.write('{Hash %dmb, Threads %d, @ %0.1fs/pos}\n'\
                            %(self.engHashOpt, self.engThreadsOpt, self.moveTimeOpt/1000.0))

            # Save result to be written later as game termination marker.
            res = game.headers['Result']

            # Loop thru the moves within this game.
            gameNode = game        
            while gameNode.variations:
                side = gameNode.board().turn
                fmvn = gameNode.board().fullmove_number             
                nextNode = gameNode.variation(0)                      
                sanMove = nextNode.san()
                complexityNumber = 0
                moveChanges = 0

                # (0) Don't start the engine analysis when fmvn is
                # below moveStart and not using a cerebellum book.
                if fmvn < self.moveStartOpt and self.bookOpt != 'cerebellum':
                    cereBookMove = None
                    self.WriteNotation(side, fmvn, sanMove, cereBookMove,
                                       None, False, None, None,
                                       complexityNumber, moveChanges)
                    gameNode = nextNode
                    continue                    

                # (1) Try to get a cerebellum book move.
                cereBookMove = None
                if self.bookOpt == 'cerebellum' and not isCereEnd:
                    # Use FEN before a move.
                    fenBeforeMove = gameNode.board().fen()
                    cereBookMove = self.GetCerebellumBookMove(fenBeforeMove)

                    # End trying to find cerebellum book move beyond BOOK_MOVE_LIMIT.
                    if cereBookMove is None and fmvn > BOOK_MOVE_LIMIT:
                        isCereEnd = True

                # (2) Don't start the engine analysis when fmvn is below moveStart.
                if fmvn < self.moveStartOpt and cereBookMove is not None:
                    self.WriteNotation(side, fmvn, sanMove, cereBookMove,
                                       None, False, None, None,
                                       complexityNumber, moveChanges)
                    gameNode = nextNode
                    continue 

                # (3) Get the posScore or the score of the player move.
                # Can be by static eval of the engine or search score of the engine
                posScore = None
                if self.evalOpt == 'static':
                    fenAfterMove = nextNode.board().fen()
                    staticScore = self.GetStaticEvalAfterMove(fenAfterMove)
                    posScore = staticScore
                elif self.evalOpt == 'search':
                    fenAfterMove = nextNode.board().fen()
                    searchScore, complexityNumber, moveChanges = self.GetSearchScoreAfterMove(fenAfterMove, side)
                    posScore = searchScore

                # (4) Let the engine searches its score and move recommendations only if
                # posScore is not winning or lossing (more than 6.0 pawns).
                engBestMove, engBestScore = None, None
                if abs(posScore) <= WIN_SCORE and self.jobOpt == 'analyze':
                    engBestMove, engBestScore = self.GetSearchScoreBeforeMove(gameNode.board().fen(), side)
                    
                # (5) If game is over by checkmate and stalemate after a move              
                isGameOver = nextNode.board().is_checkmate() or nextNode.board().is_stalemate()
                
                # (6) Write moves and comments.
                self.WriteNotation(side, fmvn, sanMove, cereBookMove,
                                   posScore, isGameOver, engBestMove, engBestScore,
                                   complexityNumber, moveChanges)

                # Read the next position.
                gameNode = nextNode

            # Write the result and a space between games.
            with open(self.outfn, 'a') as f:
                f.write('%s\n\n' %(res))

            # Read the next game.
            game = chess.pgn.read_game(pgnHandle)

        # Close the file handle.
        pgnHandle.close()

    def AnnotateEpd(self):
        """ Annotate epd file with bm, ce, acs, acd, and Ae op codes
            Ae - analyzing engine, a special op code for this script.
        """
        cntEpd = 0
        
        # Open the epd file for reading.
        with open(self.infn, 'r') as f:
            for lines in f:
                cntEpd += 1
                
                # Remove white space at beginning and end of lines.
                epdLine = lines.strip()

                # Get only first 4 fields [pieces side castle_flag ep_sq].
                epdLineSplit = epdLine.split()
                epd = ' '.join(epdLineSplit[0:4])                

                # Add hmvc and fmvn to create a FEN for the engine.
                fen = epd + ' 0 1'

                # Show progress in console.
                print('epd %d: %s' %(cntEpd, epd))

                # If this position has no legal move then we skip it.
                pos = chess.Board(fen)
                isGameOver = pos.is_checkmate() or pos.is_stalemate()
                if isGameOver:
                    # Show warning in console.
                    print('Warning! epd \"%s\"' %(epd))
                    print('has no legal move - skipped.\n')
                    continue

                # Get engine analysis.
                if self.evalOpt == 'static':
                    ce = self.GetEpdEngineStaticScore(fen)
                elif self.evalOpt != 'none':
                    acd, acs, bm, ce = self.GetEpdEngineSearchScore(fen)

                # Show progress in console.
                if self.evalOpt == 'search':
                    print('bm: %s' %(bm))
                print('ce: %+d\n' %(ce))

                # Save to output file the epd analysis.
                with open(self.outfn, 'a') as f1:
                    if self.evalOpt == 'static':
                        f1.write('%s ce %+d; c0 \"%s\"; Ae \"%s\";\n' %(epd, ce, 'ce is static eval of engine', self.engIdName))
                    elif self.evalOpt != 'none':
                        f1.write('%s acd %d; acs %d; bm %s; ce %+d; Ae \"%s\";\n'\
                                 %(epd, acd, acs, bm, ce, self.engIdName))

    def GetEpdBm(self, epdLineList):
        """ return the bm in a list format in the epd line.
            There can be more 1 bm in a given epd.
        """
        # Example epd line.
        # [pieces] [side] [castle] [ep] bm e4 Nf3; c0 "id 1";
        bmIndex = epdLineList.index('bm')

        # Extract the string beyond the bm.
        bmStartValue = ' '.join(epdLineList[bmIndex+1:])

        # Remove trailing and leading empty space in the string.
        bmStartValue = bmStartValue.strip()

        # Split at semi colon.
        semiColonSplit = bmStartValue.split(';')

        # Extract the bm by taking the value with index [0].
        bmValue = semiColonSplit[0]

        # There could be more than 1 bm so we save it in a list.
        epdBm = bmValue.split()
        return epdBm

    def IsCorrectEngineBm(self, engineBm, epdBm):
        """ Returns True or False.
            Check if engineBm is correct against epdBm list
        """
        found = False
        for ebm in epdBm:
            if engineBm == ebm:
                found = True
                break
        return found

    def GetHmvcInEpd(self, epdLine):
        """ Returns hmvc in an epd line """        
        if 'hmvc' not in epdLine:
            return '0'
        hmvcIndex = epdLine.index('hmvc')
        hmvcValue = epdLine[hmvcIndex+1]

        # Remove ';' at the end
        hmvc = hmvcValue[0:-1]
        return hmvc     

    def TestEngineWithEpd(self):
        """ Test engine with epd test suite, results will be in the output file. """
        cntEpd = 0
        cntCorrect = 0
        cntValidEpd = 0
        
        # Open the epd file for reading.
        with open(self.infn, 'r') as f:
            for lines in f:
                cntEpd += 1
                
                # Remove white space at beginning and end of lines.
                epdLine = lines.strip()

                # Get the first 4 fields [pieces side castle_flag ep_sq],
                # also search the hmvc opcode.
                epdLineSplit = epdLine.split()
                epd = ' '.join(epdLineSplit[0:4])
                hmvc = self.GetHmvcInEpd(epdLineSplit)

                # Add hmvc and fmvn to create a FEN for the engine.
                fen = epd + ' ' + hmvc + ' 1'

                # Show progress in console.
                print('EPD %d: %s' %(cntEpd, epdLine))
                print('FEN %d: %s' %(cntEpd, fen))

                # If this position has no legal move then we skip it.
                pos = chess.Board(fen)
                isGameOver = pos.is_checkmate() or pos.is_stalemate()
                if isGameOver:
                    # Show warning in console.
                    print('Warning! epd \"%s\"' %(epd))
                    print('has no legal move - skipped.\n')
                    continue

                # If the epd line has no bm then we just skip it.
                if 'bm ' not in epdLine:
                    print('Warning!! epd \"%s\"')
                    print('has no bm op code - skipped.\n')
                    continue

                # Get the bm(s) move in the epd line, epdBm is a list.
                epdBm = self.GetEpdBm(epdLineSplit)                

                # Get engine analysis, we are only interested on bm.
                acd, acs, bm, ce = self.GetEpdEngineSearchScore(fen)
                
                # There percentage correct is based on valid epd only
                cntValidEpd += 1

                # Show progress in console.
                print('engine bm: %s' %(bm))

                # Check bm of engine against the bm in epd, if found count it.
                isCorrect = self.IsCorrectEngineBm(bm, epdBm)
                if isCorrect:
                    cntCorrect += 1
                    print('correct: %d' %(cntCorrect))
                print

        # Print test summary.
        cntWrong = cntValidEpd - cntCorrect
        pctCorrect = 0.0
        if cntValidEpd:
            pctCorrect = (100.0 * cntCorrect)/cntValidEpd

        # Print summary to console
        print(':: EPD %s TEST RESULTS ::\n' %(self.infn))
        print('Total epd lines       : %d' %(cntEpd))
        print('Total tested positions: %d' %(cntValidEpd))
        print('Total correct         : %d' %(cntCorrect))
        print('Correct percentage    : %0.1f' %(pctCorrect))

        # Write to output file, that was specified in -outfile option.
        with open(self.outfn, 'a') as f:
            f.write(':: EPD %s TEST RESULTS ::\n' %(self.infn))
            f.write('Engine        : %s\n' %(self.engIdName))
            f.write('Time/pos (sec): %0.1f\n\n' %(self.moveTimeOpt/1000.0))
            
            f.write('Total epd lines       : %d\n' %(cntEpd))
            f.write('Total tested positions: %d\n' %(cntValidEpd))
            f.write('Total correct         : %d\n' %(cntCorrect))
            f.write('Correct percentage    : %0.1f\n' %(pctCorrect))
            
def main(argv):
    """ start """
    PrintProgram()

    # Initialize
    inputFile = 'src.pgn'
    outputFile = 'out_src.pgn'
    engineName = 'engine.exe'
    bookOption = 'none'   # ['none', 'cerebellum', 'polyglot']
    evalOption = 'static' # ['none', 'static', 'search']
    cereBookFile = 'Cerebellum_Light.bin'
    moveTimeOption = 0
    engHashOption = 32 # 32 mb
    engThreadsOption = 1
    moveStartOption = 8
    jobOption = 'analyze' # ['none' 'analyze', 'test']
    
    # Evaluate the command line options.
    options = EvaluateOptions(argv)
    if len(options):
        inputFile = GetOptionValue(options, '-infile', inputFile)
        outputFile = GetOptionValue(options, '-outfile', outputFile)
        engineName = GetOptionValue(options, '-eng', engineName)
        bookOption = GetOptionValue(options, '-book', bookOption)
        evalOption = GetOptionValue(options, '-eval', evalOption)
        moveTimeOption = GetOptionValue(options, '-movetime', moveTimeOption)
        engHashOption = GetOptionValue(options, '-enghash', engHashOption)
        engThreadsOption = GetOptionValue(options, '-engthreads', engThreadsOption)
        moveStartOption = GetOptionValue(options, '-movestart', moveStartOption)
        jobOption = GetOptionValue(options, '-job', jobOption)

    # Check input, output and engine files.
    CheckFiles(inputFile, outputFile, engineName)
    
    # Disable use of cerebellum book when Cerebellum_Light.bin is missing.
    if bookOption == 'cerebellum':
        if not os.path.isfile(cereBookFile):
            bookOption = 'none'
            print('Warning! cerebellum book is missing.')

    # Determine if input file is epd or pgn or None.
    if inputFile.endswith('.epd'):
        fileType = EPD_FILE
    elif inputFile.endswith('.pgn'):
        fileType = PGN_FILE
    
    # Exit if book and eval options are none and file type is pgn.
    if bookOption == 'none' and evalOption == 'none' and fileType == PGN_FILE:
        print('Error! options were not defined. Nothing has been processed.')
        sys.exit(1)

    # Exit if file type is epd and move time is 0.
    if fileType == EPD_FILE and moveTimeOption <= 0:
        print('Error! movetime is zero.')
        sys.exit(1)

    # Exit if analyzing epd with -eval none
    if fileType == EPD_FILE and evalOption == 'none' and jobOption != 'test':
        print('Error! -eval was set to none.')
        sys.exit(1)

    # Exit if input file is pgn and -job is test or none
    if fileType == PGN_FILE and jobOption != 'analyze':
        print('Error! -job was not defined with analyze.')
        print('Use -job analyze')
        sys.exit(1)
        
    # Delete existing output file.
    DeleteFile(outputFile)

    # Check Limits.
    if engThreadsOption <= 0:
        engThreadsOption = 1
        
    # Convert options to dict.
    options = {'-book': bookOption,
               '-eval': evalOption,
               '-movetime': moveTimeOption,
               '-enghash': engHashOption,
               '-engthreads': engThreadsOption,
               '-movestart': moveStartOption,
               '-job': jobOption
               }

    # Create an object of class Analyze.
    g = Analyze(inputFile, outputFile, engineName, **options)

    # Print engine id name.
    g.PrintEngineIdName()

    # Process input file depending on the format and options
    if fileType == EPD_FILE:
        if jobOption == 'test':
            g.TestEngineWithEpd()
        else:
            g.AnnotateEpd()
    elif fileType == PGN_FILE:
        g.AnnotatePgn()
    else:
        print('Warning! it is not possbile to reach here')

    print('Done!!\n')    

if __name__ == "__main__":
    main(sys.argv[1:])
