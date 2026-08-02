{-# LANGUAGE FlexibleContexts #-}
{-# LANGUAGE FlexibleInstances #-}
{-# LANGUAGE MultiParamTypeClasses #-}

module Main where

import Control.Exception (evaluate)
import Data.Functor.Identity (Identity)
import qualified Data.Set as Set
import System.CPUTime (getCPUTime)
import System.Directory (createDirectoryIfMissing)
import System.Environment (getArgs)
import System.FilePath ((</>))
import Text.Printf (printf)

import Test.Feat (Enumerable(..))
import qualified Test.Feat as F
import Test.SmallCheck.Series (Serial(..))
import qualified Test.SmallCheck.Series as S

data E2 = E20 | E21 deriving (Eq, Ord, Show, Enum, Bounded)
data E4 = E40 | E41 | E42 | E43 deriving (Eq, Ord, Show, Enum, Bounded)
data E8 = E80 | E81 | E82 | E83 | E84 | E85 | E86 | E87 deriving (Eq, Ord, Show, Enum, Bounded)
data E16 = E160 | E161 | E162 | E163 | E164 | E165 | E166 | E167
         | E168 | E169 | E1610 | E1611 | E1612 | E1613 | E1614 | E1615
         deriving (Eq, Ord, Show, Enum, Bounded)

instance Enumerable E2 where
  enumerate = F.datatype [F.c0 E20, F.c0 E21]

instance Enumerable E4 where
  enumerate = F.datatype [F.c0 E40, F.c0 E41, F.c0 E42, F.c0 E43]

instance Enumerable E8 where
  enumerate = F.datatype
    [ F.c0 E80, F.c0 E81, F.c0 E82, F.c0 E83
    , F.c0 E84, F.c0 E85, F.c0 E86, F.c0 E87
    ]

instance Enumerable E16 where
  enumerate = F.datatype
    [ F.c0 E160, F.c0 E161, F.c0 E162, F.c0 E163
    , F.c0 E164, F.c0 E165, F.c0 E166, F.c0 E167
    , F.c0 E168, F.c0 E169, F.c0 E1610, F.c0 E1611
    , F.c0 E1612, F.c0 E1613, F.c0 E1614, F.c0 E1615
    ]

instance Monad m => Serial m E2 where
  series = S.cons0 E20 S.\/ S.cons0 E21

instance Monad m => Serial m E4 where
  series = foldr1 (S.\/) (map S.cons0 [E40, E41, E42, E43])

instance Monad m => Serial m E8 where
  series = foldr1 (S.\/) (map S.cons0 [E80, E81, E82, E83, E84, E85, E86, E87])

instance Monad m => Serial m E16 where
  series = foldr1 (S.\/) (map S.cons0
    [ E160, E161, E162, E163, E164, E165, E166, E167
    , E168, E169, E1610, E1611, E1612, E1613, E1614, E1615
    ])

data Balanced = Balanced E16 E16 E8 deriving (Eq, Ord, Show)
data Imbalanced = ISmall E2 | IMedium E4 E4 | ILarge E16 E16 | IHuge E16 E16 E8 deriving (Eq, Ord, Show)
data Dependent = DAlpha E8 E16 | DBeta E16 E16 E8 | DGamma E4 E4 E4 E4 E4 E4 | DDelta E16 deriving (Eq, Ord, Show)
data Protocol = PPing E16 | PData E8 E16 E8 | PAck E4 E16 | PError E2 E4 deriving (Eq, Ord, Show)
data Action = ASearch E16 E8 | ASend E16 E16 E8 | ACompute E16 E16 | AAdmin E4 E4 E4 deriving (Eq, Ord, Show)

instance Enumerable Balanced where enumerate = F.datatype [F.c3 Balanced]
instance Enumerable Imbalanced where enumerate = F.datatype [F.c1 ISmall, F.c2 IMedium, F.c2 ILarge, F.c3 IHuge]
instance Enumerable Dependent where enumerate = F.datatype [F.c2 DAlpha, F.c3 DBeta, F.c6 DGamma, F.c1 DDelta]
instance Enumerable Protocol where enumerate = F.datatype [F.c1 PPing, F.c3 PData, F.c2 PAck, F.c2 PError]
instance Enumerable Action where enumerate = F.datatype [F.c2 ASearch, F.c3 ASend, F.c2 ACompute, F.c3 AAdmin]

instance Monad m => Serial m Balanced where series = S.cons3 Balanced
instance Monad m => Serial m Imbalanced where series = S.cons1 ISmall S.\/ S.cons2 IMedium S.\/ S.cons2 ILarge S.\/ S.cons3 IHuge
instance Monad m => Serial m Dependent where series = S.cons2 DAlpha S.\/ S.cons3 DBeta S.\/ S.cons6 DGamma S.\/ S.cons1 DDelta
instance Monad m => Serial m Protocol where series = S.cons1 PPing S.\/ S.cons3 PData S.\/ S.cons2 PAck S.\/ S.cons2 PError
instance Monad m => Serial m Action where series = S.cons2 ASearch S.\/ S.cons3 ASend S.\/ S.cons2 ACompute S.\/ S.cons3 AAdmin

ix :: Enum a => a -> Int
ix = fromEnum

mixed :: [Int] -> [Int] -> Int
mixed widths values = foldl (\acc (w, v) -> acc * w + v) 0 (zip widths values)

rankBalanced :: Balanced -> Int
rankBalanced (Balanced a b c) = mixed [16,16,8] [ix a,ix b,ix c]

rankImbalanced :: Imbalanced -> Int
rankImbalanced (ISmall a) = mixed [2] [ix a]
rankImbalanced (IMedium a b) = 2 + mixed [4,4] [ix a,ix b]
rankImbalanced (ILarge a b) = 18 + mixed [16,16] [ix a,ix b]
rankImbalanced (IHuge a b c) = 274 + mixed [16,16,8] [ix a,ix b,ix c]

rankDependent :: Dependent -> Int
rankDependent (DAlpha a b) = mixed [8,16] [ix a,ix b]
rankDependent (DBeta a b c) = 128 + mixed [16,16,8] [ix a,ix b,ix c]
rankDependent (DGamma a b c d e f) = 2176 + mixed [4,4,4,4,4,4] [ix a,ix b,ix c,ix d,ix e,ix f]
rankDependent (DDelta a) = 6272 + ix a

rankProtocol :: Protocol -> Int
rankProtocol (PPing a) = ix a
rankProtocol (PData a b c) = 16 + mixed [8,16,8] [ix a,ix b,ix c]
rankProtocol (PAck a b) = 1040 + mixed [4,16] [ix a,ix b]
rankProtocol (PError a b) = 1104 + mixed [2,4] [ix a,ix b]

rankAction :: Action -> Int
rankAction (ASearch a b) = mixed [16,8] [ix a,ix b]
rankAction (ASend a b c) = 128 + mixed [16,16,8] [ix a,ix b,ix c]
rankAction (ACompute a b) = 2176 + mixed [16,16] [ix a,ix b]
rankAction (AAdmin a b c) = 2432 + mixed [4,4,4] [ix a,ix b,ix c]

timed :: IO a -> IO (a, Integer)
timed action = do
  start <- getCPUTime
  value <- action
  end <- getCPUTime
  pure (value, end - start)

dedup :: Ord a => [a] -> [a]
dedup = go Set.empty where
  go _ [] = []
  go seen (x:xs)
    | Set.member x seen = go seen xs
    | otherwise = x : go (Set.insert x seen) xs

forceInts :: [Int] -> IO [Int]
forceInts values = do
  _ <- evaluate (length values)
  _ <- evaluate (sum values)
  pure values

writeRanks :: FilePath -> String -> Integer -> [Int] -> IO ()
writeRanks out method elapsed ranks = writeFile out $
  "#method=" ++ method ++ "\n" ++
  "#elapsed_picoseconds=" ++ show elapsed ++ "\n" ++
  unlines (map show ranks)

runOne :: (Enumerable a, Serial Identity a, Ord a) => FilePath -> String -> Int -> (a -> Int) -> IO ()
runOne out name count ranker = do
  (featRanks, featTime) <- timed $ do
    let values = [F.index (toInteger i) | i <- [0 .. count - 1]]
    forceInts (map ranker values)
  (smallRanks, smallTime) <- timed $ do
    let values = S.listSeries 20
    forceInts (dedup (map ranker values))
  if Set.fromList featRanks /= Set.fromList [0 .. count - 1]
    then error ("Feat did not cover " ++ name)
    else pure ()
  if Set.fromList smallRanks /= Set.fromList [0 .. count - 1]
    then error ("SmallCheck did not cover " ++ name ++ ", got " ++ show (length smallRanks))
    else pure ()
  writeRanks (out </> ("feat_" ++ name ++ ".txt")) "feat" featTime featRanks
  writeRanks (out </> ("smallcheck_" ++ name ++ ".txt")) "smallcheck" smallTime smallRanks
  printf "%s feat=%d smallcheck=%d\n" name (length featRanks) (length smallRanks)

main :: IO ()
main = do
  args <- getArgs
  case args of
    ["--out", out] -> do
      createDirectoryIfMissing True out
      runOne out "balanced_product" 2048 rankBalanced
      runOne out "imbalanced_choice" 2322 rankImbalanced
      runOne out "dependent_record" 6288 rankDependent
      runOne out "protocol_message" 1112 rankProtocol
      runOne out "action_space" 2496 rankAction
    _ -> error "usage: sota-haskell --out DIRECTORY"
